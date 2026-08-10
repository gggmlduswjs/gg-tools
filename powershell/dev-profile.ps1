# dev-profile.ps1 — 프로젝트 세션 격리 통일 런처 (dotfiles).
# PowerShell 프로필에서 dot-source 해서 쓴다 (install.ps1이 자동 배선).
#
#   dev bm 반품   → bookmart 격리 worktree에서 claude 자동 시작
#   dev cp 광고   → Coupang_v2 격리 worktree에서 claude 자동 시작
#   dev r         → 모든 세션(메인+워크트리) 목록에서 골라 이어하기
#   dev           → 사용법
#   (이름 생략 시 자동 명명. 기존 worktree 이름이면 재사용.)
#
# 프로젝트 위치: 기본 = <사용자>\Desktop\북마트\bookmart / <사용자>\Desktop\쿠팡\Coupang_v2.
# 다른 경로에 두는 PC면 $env:BOOKMART_ROOT / $env:COUPANG_ROOT 를 직접 지정.
# 레거시처럼 한 상위폴더 아래 bookmart / Coupang_v2 를 둘 때만 $env:DEV_PROJECTS 를 쓴다.

$desktop = Join-Path $env:USERPROFILE 'Desktop'
if ($env:BOOKMART_ROOT) {
  $Global:BookmartRoot = $env:BOOKMART_ROOT
}
elseif ($env:DEV_PROJECTS) {
  $Global:BookmartRoot = Join-Path $env:DEV_PROJECTS 'bookmart'
}
else {
  $Global:BookmartRoot = Join-Path (Join-Path $desktop '북마트') 'bookmart'
}

if ($env:COUPANG_ROOT) {
  $Global:CoupangRoot = $env:COUPANG_ROOT
}
elseif ($env:DEV_PROJECTS) {
  $Global:CoupangRoot = Join-Path $env:DEV_PROJECTS 'Coupang_v2'
}
else {
  $Global:CoupangRoot = Join-Path (Join-Path $desktop '쿠팡') 'Coupang_v2'
}

function dev {
  param([string]$proj, [string]$name)
  switch ($proj) {
    'bm' {
      if (-not $name) { $name = 's' + (Get-Date -Format 'MMddHHmm') }
      if (-not (Test-Path $Global:BookmartRoot)) { Write-Warning "bookmart 없음: $Global:BookmartRoot (필요시 `$env:DEV_PROJECTS 설정)"; return }
      Set-Location $Global:BookmartRoot
      try { devclean bm } catch { Write-Warning "정리 건너뜀: $_" }   # 아래 'cp' 주석 참고
      & (Join-Path $Global:BookmartRoot '_scripts\bmwt.ps1') start $name   # 생성/재사용 + .venv/.env provision + claude
    }
    'cp' {
      if (-not $name) { $name = 's' + (Get-Date -Format 'MMddHHmm') }
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

  # 1) 남은 변경 커밋 (worktree 격리 → add -A = 이 세션 것만)
  git -C $root add -A
  if (@(git -C $root status --porcelain).Count -gt 0) {
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
