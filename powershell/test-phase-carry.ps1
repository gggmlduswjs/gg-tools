# phase 실어보내기 검사 — 격리 worktree 로 phase 폴더가 「폴더로」 옮겨지는지.
#
# 2026-08-08 하루에 이 두 줄로 세 번 데였다. 두 실패가 **서로 반대 방향**이라 한쪽만 막으면
# 반대쪽이 열린다:
#   ① dst 가 이미 있으면  → `dst\<phase>\` 로 한 겹 들어가고 바깥은 옛 판 그대로 (#5)
#   ② dst 가 없으면      → dst 가 **파일**이 되고(마지막 소스 파일 사본) 하네스가 not found 로 죽는다
# 그래서 둘을 같이 본다. 엔진은 bookmart·Coupang_v2 공용이라 여기서 깨면 양쪽이 동시에 죽는다.
#
# ⚠️ 패턴을 베끼지 않고 **ai-engine.ps1 에서 그 두 줄을 뽑아 돌린다** — 베끼면 엔진을
#    되돌려도 이 검사는 통과하는 껍데기가 된다.

$ErrorActionPreference = 'Stop'

$engine = Join-Path $PSScriptRoot 'ai-engine.ps1'
$lines = @(Get-Content -LiteralPath $engine | Where-Object { $_ -match '^\s*(New-Item|Copy-Item)\b.*\$phaseDst' })
if ($lines.Count -ne 2) {
    throw "ai-engine.ps1 에서 phase 복사 두 줄을 못 찾았다 ($($lines.Count)줄). 패턴이 바뀌었으면 이 검사도 같이 고쳐라."
}

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("phasecarry-" + [guid]::NewGuid().ToString('N').Substring(0, 8))

# 소스 모양이 두 가지라 **깨졌을 때 증상이 다르다** — 둘 다 봐야 한다(2026-08-08 실측):
#   · 파일만        → dst 가 **파일**이 된다 (마지막 파일 사본. 실제 사고가 이 모양이었다)
#   · 서브폴더 포함 → dst 는 폴더가 되지만 내용이 **납작해진다** (`sub\nested.md` → `nested.md`)
# 파일만 있는 경우를 빼면 「dst 가 파일이 됐다」 assert 가 영원히 안 돈다.
$cases = @(
    @{ Name = '파일만 (실제 사고 모양)'; Files = @('index.json', 'step3.md') }
    @{ Name = '폴더 안 폴더 포함'; Files = @('index.json', 'step3.md', 'sub\nested.md') }
)

function Invoke-CarryLines {
    foreach ($l in $script:lines) { Invoke-Expression $l }
}

try {
    foreach ($case in $cases) {
        $tag = $case.Name
        $phaseSrc = Join-Path $tmp "src-$($cases.IndexOf($case))\회계보드-축-소급"
        foreach ($rel in $case.Files) {
            $f = Join-Path $phaseSrc $rel
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $f) | Out-Null
            Set-Content -LiteralPath $f -Value $rel
        }
        $phaseDst = Join-Path $tmp "wt-$($cases.IndexOf($case))\.dev\harness\phases\회계보드-축-소급"

        # ── ② dst 가 없는 상태 ────────────────────────────────────────
        Invoke-CarryLines
        if (-not (Test-Path -LiteralPath $phaseDst -PathType Container)) {
            throw "[$tag] dst 가 디렉터리가 아니다 — 파일이 됐다(2026-08-08 3번째 사고): $phaseDst"
        }
        foreach ($rel in $case.Files) {
            if (-not (Test-Path -LiteralPath (Join-Path $phaseDst $rel) -PathType Leaf)) {
                throw "[$tag] 실어보낸 뒤 제자리에 없다: $rel"
            }
        }

        # ── ① dst 가 이미 있는 상태 (재실행) ──────────────────────────
        Invoke-CarryLines
        $nested = Join-Path $phaseDst (Split-Path -Leaf $phaseDst)
        if (Test-Path -LiteralPath $nested) {
            throw "[$tag] 한 겹 안으로 들어갔다 — 하네스는 바깥의 옛 판을 읽는다(2026-08-08 1번째 사고): $nested"
        }
        foreach ($rel in $case.Files) {
            if (-not (Test-Path -LiteralPath (Join-Path $phaseDst $rel) -PathType Leaf)) {
                throw "[$tag] 재실행이 내용물을 날렸다: $rel"
            }
        }
        Write-Host "  ✓ $tag"
    }
    Write-Host '✓ phase 실어보내기 검사 통과 (dst 없음 → 폴더로 생성 / dst 있음 → 중첩 없음)'
}
finally {
    if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force }
}
