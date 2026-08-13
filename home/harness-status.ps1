#!/usr/bin/env pwsh
# harness-status.ps1 — 지금 도는 하네스 런을 한 줄로. 상태줄이 부른다.
#
# 왜: 전엔 "궁금하면 물어봐야" 했고, 물을 때마다 LLM 토큰이 나갔다. 상태줄에 있으면
# 안 물어도 늘 보이고 공짜다.
#
# ⚠️ 런은 **워크트리마다** 있다(`go` 가 격리해서 돌리므로). 본체의 runs 만 보면
#    2개가 돌고 있어도 0개로 보인다 — worktree 전체를 훑는다.
#
# 출력: "하네스 2: 패키지-계층-재설계 6/12 · step-자기검증 2/4"  (없으면 빈 문자열)
# ⛔ 절대 죽지 않는다 — 상태줄이 깨지면 매 10초마다 사람 눈에 거슬린다. 전부 try 로 감싼다.

[CmdletBinding()]
param(
    [string] $RepoRoot = (Get-Location).Path,
    [int]    $Max = 3            # 너무 길어지면 상태줄이 잘린다
)

$ErrorActionPreference = "SilentlyContinue"

function Test-Alive {
    param($Record)
    if (-not $Record.pid) { return $false }
    $proc = Get-Process -Id ([int]$Record.pid) -ErrorAction SilentlyContinue
    if (-not $proc) { return $false }
    # PID 재사용 방어. 옛 기록엔 pid_started_at 이 없다 — 그땐 **이름**으로 거른다:
    # 러너는 항상 pwsh 다. 실측(2026-08-08) 12:44 에 죽은 런의 pid 가 node_repl 로
    # 재사용돼 「돌고 있음」으로 보였다.
    if (-not $Record.pid_started_at) { return ($proc.ProcessName -eq "pwsh") }
    try {
        $recorded = [datetime]::Parse($Record.pid_started_at).ToUniversalTime()
        return ([math]::Abs(($proc.StartTime.ToUniversalTime() - $recorded).TotalSeconds) -le 5)
    } catch { return $true }
}

function Get-Progress {
    param([string] $LogPath)
    # 로그 꼬리에서 "Step 6/12" 를 줍는다. 파일이 커도 끝 40줄이면 충분하다.
    #
    # ⚠️ 하네스는 **0부터** 센다 — `Step N/{총계-1}`. 5단계 phase 의 마지막이 `4/4` 라
    #    상태줄에 그대로 내면 **끝난 것처럼 보인다**(2026-08-08 실제로 오해했다).
    #    상태줄은 사람이 읽는 물건이니 사람 셈(1부터)으로 바꿔 낸다: 4/4 → 5/5.
    try {
        $tail = Get-Content -LiteralPath $LogPath -Tail 40 -ErrorAction SilentlyContinue
        for ($i = $tail.Count - 1; $i -ge 0; $i--) {
            $m = [regex]::Match($tail[$i], 'Step (\d+)/(\d+)')
            if ($m.Success) {
                return "{0}/{1}" -f ([int]$m.Groups[1].Value + 1), ([int]$m.Groups[2].Value + 1)
            }
        }
    } catch { }
    return $null
}

try {
    # 이 레포의 worktree 전부 (본체 포함)
    $roots = @()
    $porcelain = @(& git -C $RepoRoot worktree list --porcelain 2>$null)
    foreach ($line in $porcelain) {
        if ($line -like "worktree *") { $roots += $line.Substring(9).Trim() }
    }
    if ($roots.Count -eq 0) { $roots = @($RepoRoot) }

    $live = @()
    foreach ($r in $roots) {
        $runsDir = Join-Path $r ".dev\harness\runs"
        if (-not (Test-Path $runsDir)) { continue }
        foreach ($f in (Get-ChildItem -Path $runsDir -File -Filter "*.json" -ErrorAction SilentlyContinue |
                        Sort-Object LastWriteTime -Descending | Select-Object -First 8)) {
            $rec = try { Get-Content -Raw $f.FullName | ConvertFrom-Json } catch { $null }
            if (-not $rec) { continue }
            if (-not (Test-Alive $rec)) { continue }
            $logPath = Join-Path $r ($rec.log -replace "/", "\")
            $prog = Get-Progress $logPath
            if (-not $prog) {
                # step 진행 표시가 없는데 살아 있다 = 구현 루프가 끝나고 **리뷰 단계**다.
                # 빈칸으로 두면 "멈춘 건가?" 로 읽힌다 — 실제로 그렇게 읽혔다(2026-08-08).
                $idx = Join-Path $r ".dev\harness\phases\$($rec.phase)\index.json"
                try {
                    $steps = (Get-Content -Raw $idx | ConvertFrom-Json).steps
                    if ($steps -and -not ($steps | Where-Object { $_.status -eq "pending" })) { $prog = "리뷰" }
                } catch { }
            }
            $live += [pscustomobject]@{ phase = $rec.phase; progress = $prog }
        }
    }

    if ($live.Count -eq 0) { return "" }

    $parts = $live | Select-Object -First $Max | ForEach-Object {
        if ($_.progress) { "{0} {1}" -f $_.phase, $_.progress } else { $_.phase }
    }
    $text = "하네스 {0}: {1}" -f $live.Count, ($parts -join " · ")
    if ($live.Count -gt $Max) { $text += " …" }
    return $text
} catch {
    return ""
}
