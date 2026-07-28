# dev-profile.ps1 — 프로젝트 세션 격리 통일 런처 (dotfiles).
# PowerShell 프로필에서 dot-source 해서 쓴다 (install.ps1이 자동 배선).
#
#   dev bm 반품   → bookmart 격리 worktree에서 claude 자동 시작
#   dev cp 광고   → Coupang_v2 격리 worktree에서 claude 자동 시작
#   dev r         → 모든 세션(메인+워크트리) 목록에서 골라 이어하기
#   dev           → 사용법
#   (이름 생략 시 자동 명명. 기존 worktree 이름이면 재사용.)
#
# 프로젝트 위치: 기본 = <사용자>\Desktop 아래 bookmart / Coupang_v2 (형제 폴더).
# 다른 경로에 두는 PC면 프로필/환경에서 $env:DEV_PROJECTS 에 상위폴더를 지정.

$base = if ($env:DEV_PROJECTS) { $env:DEV_PROJECTS } else { Join-Path $env:USERPROFILE 'Desktop' }
$Global:BookmartRoot = Join-Path $base 'bookmart'
$Global:CoupangRoot  = Join-Path $base 'Coupang_v2'

function dev {
  param([string]$proj, [string]$name)
  switch ($proj) {
    'bm' {
      if (-not $name) { $name = 's' + (Get-Date -Format 'MMddHHmm') }
      if (-not (Test-Path $Global:BookmartRoot)) { Write-Warning "bookmart 없음: $Global:BookmartRoot (필요시 `$env:DEV_PROJECTS 설정)"; return }
      Set-Location $Global:BookmartRoot
      & (Join-Path $Global:BookmartRoot '_scripts\bmwt.ps1') start $name   # 생성/재사용 + .venv/.env provision + claude
    }
    'cp' {
      if (-not $name) { $name = 's' + (Get-Date -Format 'MMddHHmm') }
      if (-not (Test-Path $Global:CoupangRoot)) { Write-Warning "Coupang_v2 없음: $Global:CoupangRoot (필요시 `$env:DEV_PROJECTS 설정)"; return }
      $siblings = Split-Path $Global:CoupangRoot -Parent
      $wt = Join-Path $siblings "Coupang_v2-wt\$name"
      Set-Location $Global:CoupangRoot
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
        $t = ($title ?? $utext ?? (Split-Path $cwd -Leaf)) -replace '\s+', ' '
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
  # 머지된 워크트리 자동 제거 + 찌꺼기 청소. 미머지/변경 있는 건 안 지우고 표시만.
  # dev clean = bm,cp 둘 다 | dev clean bm = bookmart만 | dev clean cp = Coupang_v2만
  param([string]$proj, [int]$staleDays = 14)
  $roots = switch ($proj) {
    'bm' { , $Global:BookmartRoot }
    'cp' { , $Global:CoupangRoot }
    default { $Global:BookmartRoot, $Global:CoupangRoot }
  }
  foreach ($root in $roots) {
    if (-not (Test-Path (Join-Path $root '.git'))) { Write-Warning "git repo 없음: $root"; continue }
    Write-Host "`n== $(Split-Path $root -Leaf) ==" -ForegroundColor Cyan
    $nBefore = @(git -C $root worktree list --porcelain | Where-Object { $_ -like 'worktree *' }).Count
    git -C $root worktree prune                                  # 폴더 없어진 등록 청소
    $pruned = $nBefore - @(git -C $root worktree list --porcelain | Where-Object { $_ -like 'worktree *' }).Count
    $main = (git -C $root symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>$null) -replace '^origin/', ''
    if (-not $main) { git -C $root show-ref --verify --quiet refs/heads/main; $main = if ($LASTEXITCODE -eq 0) { 'main' } else { 'master' } }
    $mainTop = (git -C $root rev-parse --show-toplevel) -replace '/', '\'

    # ★머지 판정은 반드시 origin/$main 기준. 로컬 $main 은 pull 이 안 돼 상시 뒤처지고
    # (2026-07-28 실측 10커밋), 그러면 실제로 머지된 브랜치가 전부 '미머지'로 보여
    # **아무것도 정리되지 않는다** — 북마트 로컬 64·원격 111 누적의 진짜 원인.
    git -C $root fetch origin $main -q --prune
    $mainRef = "origin/$main"

    $items = @(); $wt = $null; $br = $null                       # --porcelain 파싱
    foreach ($line in (git -C $root worktree list --porcelain)) {
      if     ($line -like 'worktree *') { $wt = ($line.Substring(9) -replace '/', '\') }
      elseif ($line -like 'branch *')   { $br = $line.Substring(7) -replace '^refs/heads/', '' }
      elseif ($line -eq '')             { if ($wt) { $items += [pscustomobject]@{ Path = $wt; Branch = $br }; $wt = $null; $br = $null } }
    }
    if ($wt) { $items += [pscustomobject]@{ Path = $wt; Branch = $br } }

    # `branch -d` 는 upstream(origin/<브랜치>) 보다 앞서면 머지됐어도 거부한다 — 로컬에 merge 커밋이
    # 더 쌓인 흔한 경우. origin/$main 의 조상임을 직접 확인했을 때만 -D 로 마무리한다(내용은 이미 landed).
    $delBranch = {
      param($b)
      git -C $root branch -d $b 2>$null | Out-Null
      if ($LASTEXITCODE -eq 0) { return $true }
      git -C $root merge-base --is-ancestor $b $mainRef 2>$null
      if ($LASTEXITCODE -ne 0) { return $false }                      # 조상 아님 = 진짜 미머지 → 남긴다
      git -C $root branch -D $b 2>$null | Out-Null
      return ($LASTEXITCODE -eq 0)
    }

    $removed = 0; $kept = 0
    foreach ($it in $items) {
      if ($it.Path -eq $mainTop -or $it.Branch -eq $main) { continue }   # 메인 워크트리는 건너뜀
      $merged = git -C $root branch --merged $mainRef --format='%(refname:short)' | Where-Object { $_ -eq $it.Branch }
      if ($merged) {
        # ⚠️ 반드시 remove 앞에. 쿠팡 wt.ps1 은 워크트리 .venv 를 본체로의 junction 으로 만든다
        # → 링크를 매단 채 폴더를 재귀 삭제하면 git 이 링크를 타고 들어가 **본체 .venv 를 파괴**한다
        # (2026-07-28 실측: Lib/ 전소. 북마트는 07-25 에 정션 생성을 아예 없애 같은 사고를 끝냈다).
        # cmd rmdir = reparse point 만 제거하고 target 은 보존. Remove-Item 은 안으로 들어갈 위험이 있어 회피.
        $venvDst = Join-Path $it.Path '.venv'
        if (Test-Path $venvDst) { cmd /c rmdir "$venvDst" 2>$null | Out-Null }

        $out = git -C $root worktree remove $it.Path 2>&1           # 변경 있으면 git이 알아서 거부(--force 안 씀)
        if ($LASTEXITCODE -eq 0) {
          & $delBranch $it.Branch | Out-Null                        # 폴더만 지우면 브랜치가 영원히 쌓인다
          Write-Host "  제거 $($it.Path)  [$($it.Branch)]" -ForegroundColor Green; $removed++
        }
        else { Write-Host "  남김(변경 있음) $($it.Path)  — $($out -join ' ')" -ForegroundColor Yellow; $kept++ }
      }
      else {
        $age = if (Test-Path $it.Path) { ((Get-Date) - (Get-Item $it.Path).LastWriteTime).Days } else { 0 }
        $note = if ($age -ge $staleDays) { "미머지, ${age}일 방치 — 확인 후 수동 삭제" } else { '미머지' }
        Write-Host "  남김($note) $($it.Path)  [$($it.Branch)]" -ForegroundColor DarkYellow; $kept++
      }
    }
    # 워크트리는 이미 없는데 남아 있는 머지 브랜치 — 누적(로컬 64·원격 111, 2026-07-28 실측)의 본체.
    # 위 루프는 '워크트리를 가진' 브랜치만 건드리므로 여기서 따로 쓸어야 한다. -d 라 미머지는 git 이 거부.
    $live = @($items | ForEach-Object { $_.Branch })
    $sweptBranches = 0
    foreach ($b in (git -C $root branch --merged $mainRef --format='%(refname:short)')) {
      if (-not $b -or $b -eq $main -or $live -contains $b) { continue }
      if (& $delBranch $b) { $sweptBranches++ }
    }
    Write-Host "  → prune $pruned, 제거 $removed, 남김 $kept, 브랜치 정리 $sweptBranches" -ForegroundColor Gray
  }
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
