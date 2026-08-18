# dev-profile.ps1 — 프로젝트 세션 격리 통일 런처 (dotfiles).
# PowerShell 프로필에서 dot-source 해서 쓴다 (install.ps1이 자동 배선).
#
#   dev bm 반품   → bookmart 격리 worktree에서 claude 자동 시작
#   bm-codex 반품 → bookmart 격리 worktree에서 codex 자동 시작
#   bmc 반품      → bm-codex 별칭
#   bmc-plan 반품 "목표" → 구현/파일작성 금지 티키타카 기획 세션으로 codex 시작
#   bmp 반품 "목표"      → bmc-plan 별칭
#   bmf                → 현재 세션의 합의안을 확정 문서/phase로 정리하라고 Codex에 보낼 문구 출력
#   bmh phase     → 하네스 dry-run 확인 후 codex로 실행
#   bmd phase     → 하네스 dry-run만
#   bmr phase     → 하네스 codex 실행만
#   bms "msg"     → 현재 worktree 변경을 명시 경로 stage→commit→push→PR merge
#   cpc 광고      → Coupang_v2 격리 worktree에서 codex 자동 시작
#   cpp 광고 "목표" → Coupang_v2 구현/파일작성 금지 티키타카 기획 세션
#   cph/cpd/cpr phase → Coupang_v2 하네스 실행(bmh/bmd/bmr와 동일)
#   cps "msg"     → 현재 Coupang worktree 변경을 명시 경로 stage→commit→push→PR merge
#   dev cp 광고   → Coupang_v2 격리 worktree에서 claude 자동 시작
#   dev r         → 모든 세션(메인+워크트리) 목록에서 골라 이어하기
#   dev           → 사용법
#   (이름 생략 시 한 줄 물어본다. 엔터 = 시각 도장으로 자동 명명. 기존 worktree 이름이면 재사용.)
#
# 프로젝트 위치: 기본 = <사용자>\Desktop\북마트\bookmart / <사용자>\Desktop\쿠팡\Coupang_v2.
# 다른 경로에 두는 PC면 $env:BOOKMART_ROOT / $env:COUPANG_ROOT 를 직접 지정.
# 레거시처럼 한 상위폴더 아래 bookmart / Coupang_v2 를 둘 때만 $env:DEV_PROJECTS 를 쓴다.

$desktop = Join-Path $env:USERPROFILE 'Desktop'
function Resolve-DevRoot([string]$EnvValue, [string]$NewDefault, [string]$LegacyDefault) {
  if ($EnvValue) { return $EnvValue }
  if (Test-Path $NewDefault) { return $NewDefault }
  if (Test-Path $LegacyDefault) { return $LegacyDefault }
  return $NewDefault
}

if ($env:DEV_PROJECTS) {
  $Global:BookmartRoot = Join-Path $env:DEV_PROJECTS 'bookmart'
  $Global:CoupangRoot = Join-Path $env:DEV_PROJECTS 'Coupang_v2'
}
else {
  $Global:BookmartRoot = Resolve-DevRoot `
    $env:BOOKMART_ROOT `
    (Join-Path (Join-Path $desktop '북마트') 'bookmart') `
    (Join-Path $desktop 'bookmart')
  $Global:CoupangRoot = Resolve-DevRoot `
    $env:COUPANG_ROOT `
    (Join-Path (Join-Path $desktop '쿠팡') 'Coupang_v2') `
    (Join-Path $desktop 'Coupang_v2')
}

# 이름을 안 주면 워크트리도 브랜치도 `s08161850` 같은 시각 도장이 되어, 목록만 봐서는 어느 자리가
# 뭘 하던 곳인지 알 수 없다(2026-08-16 실측: 쿠팡 워크트리 6개 중 3개가 시각 도장). 그래서 한 줄
# 물어본다. ★폴백은 없애지 않는다 — "일단 켜본다"도 실제 용례라 엔터로 그냥 통과시킨다.
function Read-DevName {
  $stamp = 's' + (Get-Date -Format 'MMddHHmm')
  $ans = Read-Host "이 세션에서 뭘 하나? (엔터=$stamp)"
  if (-not $ans) { return $stamp }
  return ($ans.Trim() -replace '\s+', '-')   # 공백은 git 브랜치명에 못 쓴다 → wt 생성이 실패한다
}

function dev {
  param([string]$proj, [string]$name)
  switch ($proj) {
    'bm' {
      if (-not $name) { $name = Read-DevName }
      if (-not (Test-Path $Global:BookmartRoot)) { Write-Warning "bookmart 없음: $Global:BookmartRoot (필요시 `$env:DEV_PROJECTS 설정)"; return }
      Set-Location $Global:BookmartRoot
      try { devclean bm } catch { Write-Warning "정리 건너뜀: $_" }   # 아래 'cp' 주석 참고
      & (Join-Path $Global:BookmartRoot '_scripts\bmwt.ps1') start $name   # 생성/재사용 + .venv/.env provision + claude
    }
    'cp' {
      if (-not $name) { $name = Read-DevName }
      if (-not (Test-Path $Global:CoupangRoot)) { Write-Warning "Coupang_v2 없음: $Global:CoupangRoot (필요시 `$env:DEV_PROJECTS 설정)"; return }
      $siblings = Split-Path $Global:CoupangRoot -Parent
      $wt = Join-Path $siblings "Coupang_v2-wt\$name"
      Set-Location $Global:CoupangRoot
      # ★정리는 사람이 기억해서 치는 명령이면 안 된다 — 안 치게 되고, 그래서 브랜치가 121개까지
      # 쌓였다(2026-07-28). 새 작업 시작 시점이 가장 안전하다: 메인 체크아웃에 있고 어떤 워크트리에도
      # 안 들어가 있어 Windows 잠김이 없다. 안전장치는 devclean 안에 있다(origin/main 기준 머지판정 ·
      # 미커밋 있으면 남김 · 활동 12h 게이트 · 정션 폐지). 실패해도 작업 시작은 막지 않는다.
      try { devclean cp } catch { Write-Warning "정리 건너뜀: $_" }
      if (-not (Test-Path $wt)) { & (Join-Path $Global:CoupangRoot 'wt.ps1') new $name }   # 쿠팡은 provision 안 함(설계상 .venv=메인)
      if (Test-Path $wt) {
        Set-Location $wt
        if (Get-Command claude -ErrorAction SilentlyContinue) { & claude }
        else { Write-Warning "claude 못 찾음 — 수동: cd '$wt'; claude" }
      }
    }
    { $_ -in 'r', 'resume' } { devr }   # dev r → 세션 목록에서 골라 이어하기
    { $_ -in 'clean', 'c' }  { devclean $name }   # dev clean [bm|cp] → 머지된 워크트리 정리
    { $_ -in 'harvest', 'ship' } { devharvest $name }   # dev harvest ["메시지"] → 현재 워크트리 작업을 PR로 main에 landed→배포
    default { Write-Host "사용: dev bm|cp [이름]  |  dev harvest [msg] = 현재 작업 landed→배포  |  dev r = 이어하기  |  dev clean [bm|cp] = 정리" }
  }
}

function Enter-BookmartCodexWorktree {
  param([string]$name)
  if (-not $name) { $name = Read-DevName }
  if (-not (Test-Path $Global:BookmartRoot)) {
    Write-Warning "bookmart 없음: $Global:BookmartRoot (필요시 `$env:DEV_PROJECTS 설정)"
    return $null
  }

  Set-Location $Global:BookmartRoot
  try { devclean bm } catch { Write-Warning "정리 건너뜀: $_" }
  & (Join-Path $Global:BookmartRoot '_scripts\bmwt.ps1') new $name | Out-Host

  $siblings = Split-Path $Global:BookmartRoot -Parent
  $wt = Join-Path $siblings "bookmart-wt\$name"
  if (-not (Test-Path $wt)) {
    Write-Warning "worktree 없음: $wt"
    return $null
  }

  Set-Location $wt
  return $wt
}

function bm-codex {
  # bookmart 전용 Codex 런처. Claude의 `dev bm <name>`과 같은 bmwt/wt-engine을 써서
  # ../bookmart-wt/<name> 아래에 격리 checkout을 만들고, 그 안에서 codex를 시작한다.
  param([string]$name)
  $wt = Enter-BookmartCodexWorktree $name
  if (-not $wt) { return }
  if (Get-Command codex -ErrorAction SilentlyContinue) { & codex }
  else { Write-Warning "codex 못 찾음 — 수동: cd '$wt'; codex" }
}

function bmc {
  param([string]$name)
  bm-codex $name
}

function bmc-plan {
  # Claude의 "처음 플랫 모드로 길게 기획"을 Codex initial prompt로 자동 주입한다.
  # 이 명령은 티키타카 전용이다. 파일 작성은 사용자가 세션 안에서 확정 지시를 한 뒤에만 한다.
  # 사용: bmc-plan <worktree-name> "목표 설명"
  param(
    [string]$name,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$ObjectiveParts
  )
  if (-not $name) { $name = Read-DevName }
  $objective = ($ObjectiveParts -join ' ').Trim()
  if (-not $objective) {
    $objective = Read-Host "목표"
  }
  if (-not $objective) {
    Write-Warning "목표가 비어 있어 중단"
    return
  }

  $wt = Enter-BookmartCodexWorktree $name
  if (-not $wt) { return }

  $prompt = @"
이번 세션은 구현 금지. 파일 작성도 금지. 먼저 긴 기획 티키타카만 한다.

목표:
$objective

작업 계약:
1. AGENTS.md와 CLAUDE.md를 먼저 읽고, 작업 대상 앱의 CLAUDE.md가 있으면 우선한다.
2. 관련 .dev/research/{fe,be,arch}/ 와 .dev/plans/{fe,be,arch}/ 문서를 찾아 중복 구현과 완료/폐기 문서를 확인한다.
3. 화면, 표, 토스트, 정렬, 모달, CSS, 템플릿을 건드릴 가능성이 있으면 docs/reference/공용_부품.md 와 UI/UX 관련 규칙을 먼저 확인한다.
4. 경쟁 패턴/deprecated 여부는 docs/DETOX_REGISTRY.md에서 확인한다.
5. 코드 수정, 문서 작성/수정, 하네스 phase 작성, 테스트, 커밋, push는 하지 않는다.

대화 방식:
1. 먼저 읽은 파일과 기존 계획/중복 패턴을 짧게 보고한다.
2. 구현 범위, 제외 범위, 위험한 선택지를 질문/제안 형태로 정리한다.
3. 사용자가 방향을 고르면 계획안을 대화로만 다듬는다.
4. 사용자가 "확정", "문서화", "phase 만들어", "하네스 준비해", "ㄱㄱ"처럼 명시적으로 말하기 전까지 파일을 만들거나 고치지 않는다.

사용자가 확정 지시를 하면 그때 할 일:
1. .dev/research/<axis>/<name>_research.md 작성 또는 기존 문서 갱신
2. .dev/plans/<axis>/<name>_plan.md 작성 또는 기존 문서 갱신
3. plan에 "Codex 인수인계" 섹션 작성
4. 실행이 여러 독립 step으로 나뉘면 .dev/harness/phases/<phase>/index.json 과 step<N>.md 작성
5. phase 이름은 ASCII kebab-case를 선호한다.
6. 각 step<N>.md에는 먼저 읽을 파일, 수정 예상 파일, 재사용할 함수/서비스/컴포넌트, 건드리지 말 것, 실행 가능한 검증 명령을 포함한다.
7. worktree 안에서 실행할 것이므로 실행 명령은 python .dev/harness/execute.py <phase> --no-branch --provider codex 기준으로 적는다.

첫 응답:
- "아직 파일은 만들지 않는다"라고 명시한다.
- 읽을 문서/파일 목록과 확인할 쟁점을 먼저 제시한다.
"@

  if (Get-Command codex -ErrorAction SilentlyContinue) { & codex $prompt }
  else { Write-Warning "codex 못 찾음 — 수동: cd '$wt'; codex <긴 프롬프트>" }
}

function bmp {
  param(
    [string]$name,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$ObjectiveParts
  )
  bmc-plan $name @ObjectiveParts
}

function bmf {
  # bmp 세션 안에 붙여 넣는 확정 지시. 클립보드 실패 환경도 있어서 화면 출력만 한다.
  @"
좋아. 이제 이 합의안을 확정 계획으로 정리해.

해야 할 일:
1. .dev/research/<axis>/<name>_research.md 작성 또는 기존 문서 갱신
2. .dev/plans/<axis>/<name>_plan.md 작성 또는 기존 문서 갱신
3. plan에 "Codex 인수인계" 섹션 작성
4. 실행이 여러 독립 step으로 나뉘면 .dev/harness/phases/<phase>/index.json 과 step<N>.md 작성

금지:
- 앱 코드 구현 금지
- 테스트 실행 금지
- 커밋/push 금지
- 운영 DB write/SMS 실제 발송/마이그레이션 적용 금지

완료 보고:
- 만든/갱신한 research/plan/phase 파일
- 구현 전에 사람이 확인해야 할 범위 리스크
- 다음에 실행할 정확한 명령:
  bmd <phase>
  bmh <phase>
"@
}

function Get-BookmartPhaseName {
  param([string]$phase)
  if ($phase) { return $phase }

  $phaseRoot = Join-Path (Get-Location) '.dev\harness\phases'
  if (-not (Test-Path $phaseRoot)) {
    Write-Warning "phase 폴더 없음: $phaseRoot"
    return $null
  }

  $rows = @()
  foreach ($dir in Get-ChildItem -LiteralPath $phaseRoot -Directory | Where-Object { $_.Name -notin @('_archive', '_triage') }) {
    $index = Join-Path $dir.FullName 'index.json'
    if (-not (Test-Path $index)) { continue }
    try {
      $json = Get-Content -LiteralPath $index -Raw | ConvertFrom-Json
      $pending = @($json.steps | Where-Object { $_.status -eq 'pending' }).Count
      $rows += [pscustomobject]@{ Name = $dir.Name; Pending = $pending }
    }
    catch {
      $rows += [pscustomobject]@{ Name = $dir.Name; Pending = '?' }
    }
  }

  $rows = @($rows | Sort-Object Name)
  if (-not $rows) {
    Write-Warning '실행 가능한 phase 후보가 없음'
    return $null
  }
  for ($i = 0; $i -lt $rows.Count; $i++) {
    '{0,2}  {1,-32} pending={2}' -f ($i + 1), $rows[$i].Name, $rows[$i].Pending
  }

  $pick = Read-Host "`nphase 번호 또는 이름 (취소=Enter)"
  if (-not $pick) { return $null }
  if ($pick -match '^\d+$') {
    $idx = [int]$pick - 1
    if ($idx -ge 0 -and $idx -lt $rows.Count) { return $rows[$idx].Name }
    Write-Warning '범위 밖 번호'
    return $null
  }
  return $pick.Trim()
}

function Invoke-BookmartHarness {
  param(
    [string]$phase,
    [switch]$DryRun,
    [switch]$Run
  )
  $phase = Get-BookmartPhaseName $phase
  if (-not $phase) { return }

  $cmd = @('.dev/harness/execute.py', $phase, '--no-branch', '--provider', 'codex')
  if ($DryRun) { $cmd += '--dry-run' }
  python @cmd
}

function bmd {
  param([string]$phase)
  Invoke-BookmartHarness $phase -DryRun
}

function bmr {
  param([string]$phase)
  Invoke-BookmartHarness $phase -Run
}

function bmh {
  # dry-run 프롬프트를 먼저 보여준 뒤 같은 phase를 바로 실행한다.
  param([string]$phase)
  $phase = Get-BookmartPhaseName $phase
  if (-not $phase) { return }

  Invoke-BookmartHarness $phase -DryRun
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "dry-run 실패: $phase"
    return
  }

  $ans = Read-Host "`n실행할까? (Enter/ㄱㄱ/y=실행, n=중단)"
  if ($ans -and $ans -notmatch '^(y|Y|ㄱㄱ|go|GO)$') {
    Write-Host '중단'
    return
  }

  Invoke-BookmartHarness $phase -Run
}

function Get-GitPorcelainPath {
  param([string]$line)
  $p = $line.Substring(3)
  if ($p -match ' -> ') { $p = ($p -split ' -> ', 2)[1] }
  return $p.Trim('"')
}

function bms {
  # 현재 worktree 작업을 commit -> push -> PR merge 한다.
  # git add -A 금지 계약을 지키기 위해 status에 나온 파일을 경로 배열로 만든 뒤 명시적으로 add한다.
  param([string]$Message)

  $root = git rev-parse --show-toplevel 2>$null
  if (-not $root) { Write-Warning 'git repo 아님 — worktree 폴더 안에서 실행해라.'; return }

  $branch = (git -C $root rev-parse --abbrev-ref HEAD).Trim()
  $main = (git -C $root symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>$null) -replace '^origin/', ''
  if (-not $main) { $main = 'main' }
  if ($branch -eq $main) { Write-Warning "$main 브랜치에선 bms 금지 — worktree 브랜치에서 실행해라."; return }
  if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { Write-Warning 'gh CLI 필요 — PR 생성/머지에 씀.'; return }

  $dirty = @(git -C $root status --porcelain)
  if ($dirty.Count -gt 0) {
    Write-Host "`n담을 변경 $($dirty.Count)건 — 내가 고친 것만 있는지 확인:" -ForegroundColor Yellow
    $dirty | ForEach-Object { Write-Host "  $_" }
    $ans = Read-Host "`n위 파일을 명시 경로로 stage 한다 (Enter=진행 · n=중단)"
    if ($ans -match '^\s*[nN]') { Write-Host '중단'; return }

    $paths = @($dirty | ForEach-Object { Get-GitPorcelainPath $_ } | Where-Object { $_ })
    if (-not $paths) { Write-Warning 'stage할 경로를 못 찾음'; return }
    git -C $root add -- @paths
    if ($LASTEXITCODE -ne 0) { Write-Warning 'git add 실패'; return }

    git -C $root diff --cached --stat
    $ans = Read-Host "`n이 staged diff로 commit 한다 (Enter=진행 · n=중단)"
    if ($ans -match '^\s*[nN]') { Write-Host '중단 — staged 상태는 유지됨'; return }

    if (-not $Message) { $Message = Read-Host '커밋 메시지' }
    if (-not $Message) { Write-Warning '커밋 메시지 없음 — 중단'; return }
    $env:BOOKMART_HOOK_OK = '1'
    git -C $root commit -m $Message
    Remove-Item Env:\BOOKMART_HOOK_OK -ErrorAction SilentlyContinue
    if ($LASTEXITCODE -ne 0) { Write-Warning 'commit 실패'; return }
  }
  else {
    Write-Host '커밋할 변경 없음 — 기존 커밋으로 진행'
  }

  git -C $root fetch origin $main
  if ($LASTEXITCODE -ne 0) { Write-Warning 'fetch 실패'; return }
  git -C $root rebase "origin/$main"
  if ($LASTEXITCODE -ne 0) {
    git -C $root rebase --abort 2>$null
    Write-Warning "rebase 충돌 — 수동 해결 필요. push/merge 안 함."
    return
  }

  if ((git -C $root rev-list --count "origin/$main..$branch").Trim() -eq '0') {
    Write-Host "$main 과 동일 — push/merge할 커밋 없음."
    return
  }

  git -C $root push -u origin $branch
  if ($LASTEXITCODE -ne 0) { Write-Warning 'push 실패'; return }

  Push-Location $root
  try {
    gh pr create --fill --head $branch --base $main 2>$null
    $prUrl = gh pr view $branch --json url -q .url 2>$null
    gh pr merge $branch --merge
    if ($LASTEXITCODE -ne 0) {
      Write-Warning "PR 머지 실패. PR: $prUrl"
      return
    }
  }
  finally {
    Pop-Location
  }

  Write-Host "OK  $branch -> $main 머지. PR: $prUrl" -ForegroundColor Green
  Write-Host "정리: dev clean bm" -ForegroundColor Gray
}

function Enter-CoupangCodexWorktree {
  param([string]$name)
  if (-not $name) { $name = Read-DevName }
  if (-not (Test-Path $Global:CoupangRoot)) {
    Write-Warning "Coupang_v2 없음: $Global:CoupangRoot (필요시 `$env:DEV_PROJECTS 설정)"
    return $null
  }

  $siblings = Split-Path $Global:CoupangRoot -Parent
  $wt = Join-Path $siblings "Coupang_v2-wt\$name"
  Set-Location $Global:CoupangRoot
  try { devclean cp } catch { Write-Warning "정리 건너뜀: $_" }
  if (-not (Test-Path $wt)) { & (Join-Path $Global:CoupangRoot 'wt.ps1') new $name | Out-Host }
  if (-not (Test-Path $wt)) {
    Write-Warning "worktree 없음: $wt"
    return $null
  }

  Set-Location $wt
  return $wt
}

function cp-codex {
  param([string]$name)
  $wt = Enter-CoupangCodexWorktree $name
  if (-not $wt) { return }
  if (Get-Command codex -ErrorAction SilentlyContinue) { & codex }
  else { Write-Warning "codex 못 찾음 — 수동: cd '$wt'; codex" }
}

function cpc {
  param([string]$name)
  cp-codex $name
}

function cp-plan {
  param(
    [string]$name,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$ObjectiveParts
  )
  if (-not $name) { $name = Read-DevName }
  $objective = ($ObjectiveParts -join ' ').Trim()
  if (-not $objective) { $objective = Read-Host "목표" }
  if (-not $objective) { Write-Warning "목표가 비어 있어 중단"; return }

  $wt = Enter-CoupangCodexWorktree $name
  if (-not $wt) { return }

  $prompt = @"
이번 세션은 구현 금지. 파일 작성도 금지. 먼저 긴 기획 티키타카만 한다.

목표:
$objective

작업 계약:
1. AGENTS.md와 CLAUDE.md를 먼저 읽고, 작업 대상 앱/모듈 CLAUDE.md가 있으면 우선한다.
2. 관련 .dev/research/{fe,be,arch}/ 와 .dev/plans/{fe,be,arch}/ 문서를 찾아 중복 구현과 완료/폐기 문서를 확인한다.
3. 코드 수정, 문서 작성/수정, 하네스 phase 작성, 테스트, 커밋, push는 하지 않는다.

대화 방식:
1. 먼저 읽은 파일과 기존 계획/중복 패턴을 짧게 보고한다.
2. 구현 범위, 제외 범위, 위험한 선택지를 질문/제안 형태로 정리한다.
3. 사용자가 방향을 고르면 계획안을 대화로만 다듬는다.
4. 사용자가 "확정", "문서화", "phase 만들어", "하네스 준비해", "ㄱㄱ"처럼 명시적으로 말하기 전까지 파일을 만들거나 고치지 않는다.

사용자가 확정 지시를 하면 그때 할 일:
1. .dev/research/<axis>/<name>_research.md 작성 또는 기존 문서 갱신
2. .dev/plans/<axis>/<name>_plan.md 작성 또는 기존 문서 갱신
3. plan에 "Codex 인수인계" 섹션 작성
4. 실행이 여러 독립 step으로 나뉘면 .dev/harness/phases/<phase>/index.json 과 step<N>.md 작성
5. worktree 안에서 실행할 것이므로 실행 명령은 python .dev/harness/execute.py <phase> --no-branch --provider codex 기준으로 적는다.

첫 응답:
- "아직 파일은 만들지 않는다"라고 명시한다.
- 읽을 문서/파일 목록과 확인할 쟁점을 먼저 제시한다.
"@

  if (Get-Command codex -ErrorAction SilentlyContinue) { & codex $prompt }
  else { Write-Warning "codex 못 찾음 — 수동: cd '$wt'; codex <긴 프롬프트>" }
}

function Invoke-CoupangPlanShortcut {
  param(
    [string]$name,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$ObjectiveParts
  )
  cp-plan $name @ObjectiveParts
}
Remove-Item Alias:cpp -Force -ErrorAction SilentlyContinue
Set-Alias -Name cpp -Value Invoke-CoupangPlanShortcut -Force

function cpf {
  bmf
}

function cpd {
  param([string]$phase)
  bmd $phase
}

function cpr {
  param([string]$phase)
  bmr $phase
}

function cph {
  param([string]$phase)
  bmh $phase
}

function cps {
  param([string]$Message)
  bms $Message
}

function devr {
  # 모든 bookmart/Coupang 세션(메인+워크트리)을 한 목록에서 골라 resume.
  # --resume은 현재 폴더 세션만 보여줘서, 워크트리 세션을 메인에서 못 봄 → 이걸로 통합.
  param([int]$top = 20)
  $root = Join-Path $env:USERPROFILE '.claude\projects'
  $rows = foreach ($d in Get-ChildItem $root -Directory | Where-Object Name -match 'bookmart|Coupang') {
    foreach ($f in Get-ChildItem $d.FullName -Filter *.jsonl -File) {
      $sid = $cwd = $title = $utext = $null
      foreach ($line in [System.IO.File]::ReadLines($f.FullName)) {   # 지연 읽기 — 필드 찾으면 즉시 중단
        if ($line -notmatch '"(cwd|sessionId|aiTitle|summary)"' -and $line -notmatch '"type":"user"') { continue }
        try { $o = $line | ConvertFrom-Json } catch { continue }
        if (-not $sid   -and $o.sessionId)          { $sid   = $o.sessionId }
        if (-not $cwd   -and $o.cwd)                { $cwd   = $o.cwd }
        if (-not $title -and $o.type -eq 'ai-title') { $title = $o.aiTitle }   # Claude Code 자동 제목
        if (-not $title -and $o.type -eq 'summary')  { $title = $o.summary }
        if (-not $utext -and $o.type -eq 'user') {                             # 폴백: 첫 사용자 메시지
          $c = $o.message.content
          $utext = if ($c -is [string]) { $c } else { ($c | Where-Object type -eq 'text' | Select-Object -First 1).text }
        }
        if ($sid -and $cwd -and $title) { break }
      }
      if ($sid -and $cwd) {
        $t = $title
        if ([string]::IsNullOrWhiteSpace($t)) { $t = $utext }
        if ([string]::IsNullOrWhiteSpace($t)) { $t = Split-Path $cwd -Leaf }
        $t = $t -replace '\s+', ' '
        if ($t.Length -gt 50) { $t = $t.Substring(0, 50) + '…' }
        [pscustomobject]@{ Time = $f.LastWriteTime; Cwd = $cwd; Sid = $sid; Title = $t.Trim() }
      }
    }
  }
  $rows = @($rows | Sort-Object Time -Descending | Select-Object -First $top)
  if (-not $rows) { Write-Warning '세션 없음'; return }
  for ($i = 0; $i -lt $rows.Count; $i++) {
    $r = $rows[$i]
    '{0,2}  {1:MM-dd HH:mm}  {2,-24}  {3}' -f ($i + 1), $r.Time, (Split-Path $r.Cwd -Leaf), $r.Title
  }
  $pick = Read-Host "`n번호 (취소=Enter)"
  if (-not $pick) { return }
  $sel = $rows[[int]$pick - 1]
  if (-not $sel) { Write-Warning '범위 밖 번호'; return }
  if (-not (Test-Path $sel.Cwd)) { Write-Warning "폴더 없음(워크트리 삭제됨?): $($sel.Cwd)"; return }
  Set-Location $sel.Cwd
  claude --resume $sel.Sid
}

function devclean {
  # 머지된 워크트리·브랜치 정리. 판정과 삭제는 전부 **공용 엔진**(wt-engine.ps1)이 한다 —
  # 예전엔 여기에 따로 구현돼 있어서 엔진만 아는 것(squash 머지 오판 → Get-BranchLanded)을
  # 못 받았고, 엔진은 반대로 여기만 알던 브랜치 쓸기를 못 받았다(2026-07-28 통합).
  # dev clean = bm,cp 둘 다 | dev clean bm|cp = 하나만.  뒤에 --now 붙이면 조용함게이트 무시.
  param([string]$proj, [Parameter(ValueFromRemainingArguments = $true)]$extra)
  $bmScript = Join-Path '_scripts' 'bmwt.ps1'
  $targets = switch ($proj) {
    'bm' { , @{ root = $Global:BookmartRoot; script = $bmScript } }
    'cp' { , @{ root = $Global:CoupangRoot;  script = 'wt.ps1' } }
    default {
      @{ root = $Global:BookmartRoot; script = $bmScript },
      @{ root = $Global:CoupangRoot;  script = 'wt.ps1' }
    }
  }
  foreach ($t in $targets) {
    if (-not (Test-Path (Join-Path $t.root '.git'))) { Write-Warning "git repo 없음: $($t.root)"; continue }
    Write-Host ''
    Write-Host "== $(Split-Path $t.root -Leaf) ==" -ForegroundColor Cyan
    Push-Location $t.root
    # --apply 고정: dev clean 은 '치워라'는 뜻이다(엔진 단독 호출은 dry-run 이 기본).
    try { & (Join-Path $t.root $t.script) prune --apply @extra }
    catch { Write-Warning "정리 실패: $_" }
    finally { Pop-Location }
  }
}

function 현황 {
  # 이 폴더의 이해 아티팩트(파일트리·omm 뷰어·AI준비도·강의)를 브라우저 탭으로 연다.
  # 인자 없으면 현재 폴더 — 하위 폴더에서 쳐도 스크립트가 git 루트로 올려잡는다.  현황 [-Proj <경로>]
  # 런처는 .claude(로컬, 미동기) 에 있으므로 PC 따라 없을 수 있다.
  $s = Join-Path $env:USERPROFILE '.claude\understand-any.ps1'
  if (-not (Test-Path $s)) { Write-Warning "런처 없음: $s"; return }
  & $s @args
}

function devharvest {
  # 현재 워크트리 작업을 PR로 main에 landed → 자동배포. 어느 프로젝트든 "지금 있는 폴더"의 repo 기준.
  # ★명시적 전용(자동 아님). 어느 단계든 실패하면 즉시 중단, 아무것도 안 밀어. rebase 충돌은 자동해결 안 함(수동).
  # 병렬 lifecycle:  dev cp(생성) → 작업 → dev harvest(landed→배포) → dev clean cp(정리).
  param([string]$Message)
  $root = git rev-parse --show-toplevel 2>$null
  if (-not $root) { Write-Warning 'git repo 아님 — 워크트리 폴더 안에서 실행해라.'; return }
  $branch = (git -C $root rev-parse --abbrev-ref HEAD).Trim()
  $main = (git -C $root symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>$null) -replace '^origin/', ''
  if (-not $main) { $main = 'main' }
  if ($branch -eq $main) { Write-Warning "$main 브랜치에선 harvest 불가 — 워크트리 안에서 실행."; return }
  if (-not (Get-Command gh -EA SilentlyContinue)) { Write-Warning 'gh CLI(github) 필요 — PR 생성/머지에 씀.'; return }

  # 1) 남은 변경 커밋 — ★담기 전에 눈으로 보여주고 확인받는다.
  #    ⛔ 예전엔 묻지 않고 `git add -A` 였다. "worktree 격리 = 이 세션 것만" 이라는 전제였는데
  #    그 전제가 깨진다: 2026-08-13 에 두 세션이 한 워크트리를 같이 쓰다 남의 미커밋 3파일이
  #    딸려 들어갔고, 그게 이미 걷어낸 코드라 그대로 갔으면 **지운 파일이 되살아났다.**
  #    훅이 만드는 산출물(메모리 미러 등)도 늘 떠 있어 조용히 섞인다.
  #    harvest 는 **머지·배포까지 자동으로 가므로 사후 경고로는 늦다** — 여기서 한 번 세운다.
  $dirty = @(git -C $root status --porcelain)
  if ($dirty.Count -gt 0) {
    Write-Host "`n담을 변경 $($dirty.Count)건 — 내가 고친 것만 있는지 봐라:" -ForegroundColor Yellow
    $dirty | ForEach-Object { Write-Host "  $_" }
    $ans = Read-Host "`n전부 담아서 landed 한다 (엔터=진행 · n=중단)"
    if ($ans -match '^\s*[nN]') {
      Write-Host '중단 — 아무것도 안 밀었다. 필요한 것만 직접 add/commit 한 뒤 다시 실행해라.'
      return
    }
    git -C $root add -A
    if (-not $Message) { $Message = "harvest: $branch landed" }
    git -C $root commit -q -m $Message; Write-Host "커밋: $Message"
  }
  else { Write-Host '커밋할 변경 없음 — 기존 커밋으로 진행' }

  # 2) 최신 main 흡수 (★동기화 지점 — 남이 landed한 걸 여기서 흡수). 충돌 = 같은 파일 → 수동
  git -C $root fetch origin $main -q
  git -C $root rebase "origin/$main"
  if ($LASTEXITCODE -ne 0) {
    git -C $root rebase --abort 2>$null
    Write-Warning "rebase 충돌 — 다른 세션이 같은 파일 건드림. 수동 해결 필요. (아무것도 안 밀었음)"; return
  }

  # 3) landed할 커밋 있나
  if ((git -C $root rev-list --count "origin/$main..$branch").Trim() -eq '0') {
    Write-Host "$main 과 동일 — landed할 커밋 없음."; return
  }

  # 4) push → PR → 머지(merge커밋: dev clean 이 머지판정 가능) → 자동배포
  git -C $root push -u origin $branch
  if ($LASTEXITCODE -ne 0) { Write-Warning 'push 실패 — 원격/인증 확인.'; return }
  Push-Location $root
  try {
    gh pr create --fill --head $branch --base $main 2>$null   # 이미 PR 있으면 무시
    $prUrl = gh pr view $branch --json url -q .url 2>$null
    gh pr merge $branch --merge
    if ($LASTEXITCODE -ne 0) { Write-Warning "PR 머지 실패(충돌/CI/권한). PR: $prUrl — 확인 후 재시도."; return }
  }
  finally { Pop-Location }
  Write-Host "OK  $branch -> $main 머지 -> 자동배포 진입.  PR: $prUrl" -ForegroundColor Green
  Write-Host "→ 폴더 정리(머지된 워크트리 일괄):  dev clean cp" -ForegroundColor Gray
}
