#!/usr/bin/env pwsh
# Get-AllRunRecords 체크 — 격리 worktree 로 옮겨 도는 런이 tasks·tail 에서 보이는가.
#   돌리기: pwsh powershell/Test-AllRunRecords.ps1
#   실패하면 exit 1. 임시 레포는 항상 지운다.
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "ai-engine.ps1")

function Assert {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw "FAIL: $Message" }
    Write-Host "  ok: $Message"
}

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("ai-engine-check-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
$mainRoot = Join-Path $tmp "main"
$sideRoot = Join-Path $tmp "side"

function New-FakeRun {
    param([string] $RepoPath, [string] $Id, [int] $ProcessId, [datetime] $WriteTime)

    $runs = Join-Path $RepoPath ".dev\harness\runs"
    New-Item -ItemType Directory -Force -Path $runs | Out-Null
    Set-Content -Path (Join-Path $runs "$Id.log") -Value "AI_EXIT_CODE=0"
    $meta = Join-Path $runs "$Id.json"
    [pscustomobject]@{
        id    = $Id
        pid   = $ProcessId
        repo  = $RepoPath
        phase = $Id
        log   = ".dev/harness/runs/$Id.log"
    } | ConvertTo-Json -Depth 4 | Set-Content -Path $meta
    (Get-Item $meta).LastWriteTime = $WriteTime
}

Push-Location
try {
    New-Item -ItemType Directory -Force -Path $mainRoot | Out-Null
    & git -C $mainRoot init -q --initial-branch=base
    & git -C $mainRoot config user.email "check@example.invalid"
    & git -C $mainRoot config user.name "check"
    Set-Content -Path (Join-Path $mainRoot "README.md") -Value "check"
    & git -C $mainRoot add README.md
    & git -C $mainRoot commit -qm "init"
    & git -C $mainRoot worktree add -q $sideRoot -b side HEAD
    if ($LASTEXITCODE -ne 0) { throw "임시 worktree 생성 실패" }

    # 본체엔 낡은 런, 격리 worktree 엔 최신 런. pid 는 「살아 있는」 쪽을 격리 worktree 에 둬
    # Get-LiveRunRecords 가 그걸 못 봐야 한다는 것까지 잰다.
    New-FakeRun -RepoPath $mainRoot -Id "older-main" -ProcessId 999999 -WriteTime (Get-Date).AddMinutes(-10)
    New-FakeRun -RepoPath $sideRoot -Id "newer-side" -ProcessId $PID -WriteTime (Get-Date).AddMinutes(-1)

    Set-RepoRoot $mainRoot

    $records = @(Get-AllRunRecords)
    $ids = @($records | ForEach-Object { $_.id })
    Assert ($records.Count -eq 2) "본체에서 수집하면 두 worktree 의 런이 다 나온다 (got: $($ids -join ', '))"

    # 남의 레코드를 `Join-Path $Root` 로 풀면 없는 파일을 가리킨다 — _root 로 풀려야 한다.
    foreach ($r in $records) {
        $logPath = Join-Path (Get-RunRecordRoot $r) ($r.log -replace "/", "\")
        Assert (Test-Path $logPath) "$($r.id) 의 로그 경로가 실제 파일로 풀린다"
    }

    Assert ($records[0].id -eq "newer-side") "LastWriteTime 내림차순 정렬 (첫 줄: $($records[0].id))"

    # ⛔ go·stop 회귀 방어 — Get-LiveRunRecords 는 이 체크아웃만 봐야 한다.
    #    (전체를 보면 go 가 이 체크아웃을 바쁘다고 오판하고, stop -All 이 남의 런을 죽인다.)
    $live = @(Get-LiveRunRecords)
    Assert ($live.Count -eq 0) "Get-LiveRunRecords 는 옆 worktree 의 살아 있는 런을 안 본다"

    $limited = @(Get-AllRunRecords -Limit 1)
    Assert ($limited.Count -eq 1 -and $limited[0].id -eq "newer-side") "-Limit 은 파싱 전에 최신부터 자른다"

    Write-Host ""
    Write-Host "PASS: Get-AllRunRecords"
} finally {
    Pop-Location
    if (Test-Path $mainRoot) { & git -C $mainRoot worktree prune 2>&1 | Out-Null }
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
