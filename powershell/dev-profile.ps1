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
  if (-not $name) { $name = 's' + (Get-Date -Format 'MMddHHmm') }
  switch ($proj) {
    'bm' {
      if (-not (Test-Path $Global:BookmartRoot)) { Write-Warning "bookmart 없음: $Global:BookmartRoot (필요시 `$env:DEV_PROJECTS 설정)"; return }
      Set-Location $Global:BookmartRoot
      & (Join-Path $Global:BookmartRoot '_scripts\bmwt.ps1') start $name   # 생성/재사용 + .venv/.env provision + claude
    }
    'cp' {
      if (-not (Test-Path $Global:CoupangRoot)) { Write-Warning "Coupang_v2 없음: $Global:CoupangRoot (필요시 `$env:DEV_PROJECTS 설정)"; return }
      $siblings = Split-Path $Global:CoupangRoot -Parent
      $wt = Join-Path $siblings "Coupang_v2-$name"
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
    default { Write-Host "사용: dev bm|cp [이름]   |   dev r = 세션 이어하기   |   dev clean [bm|cp] = 워크트리 정리   (bm=bookmart, cp=Coupang_v2)" }
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
    git -C $root worktree prune                                  # 폴더 없어진 등록 청소
    $main = (git -C $root symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>$null) -replace '^origin/', ''
    if (-not $main) { git -C $root show-ref --verify --quiet refs/heads/main; $main = if ($LASTEXITCODE -eq 0) { 'main' } else { 'master' } }
    $mainTop = (git -C $root rev-parse --show-toplevel) -replace '/', '\'

    $items = @(); $wt = $null; $br = $null                       # --porcelain 파싱
    foreach ($line in (git -C $root worktree list --porcelain)) {
      if     ($line -like 'worktree *') { $wt = ($line.Substring(9) -replace '/', '\') }
      elseif ($line -like 'branch *')   { $br = $line.Substring(7) -replace '^refs/heads/', '' }
      elseif ($line -eq '')             { if ($wt) { $items += [pscustomobject]@{ Path = $wt; Branch = $br }; $wt = $null; $br = $null } }
    }
    if ($wt) { $items += [pscustomobject]@{ Path = $wt; Branch = $br } }

    $removed = 0; $kept = 0
    foreach ($it in $items) {
      if ($it.Path -eq $mainTop -or $it.Branch -eq $main) { continue }   # 메인 워크트리는 건너뜀
      $merged = git -C $root branch --merged $main --format='%(refname:short)' | Where-Object { $_ -eq $it.Branch }
      if ($merged) {
        $out = git -C $root worktree remove $it.Path 2>&1           # 변경 있으면 git이 알아서 거부(--force 안 씀)
        if ($LASTEXITCODE -eq 0) { Write-Host "  제거 $($it.Path)  [$($it.Branch)]" -ForegroundColor Green; $removed++ }
        else { Write-Host "  남김(변경 있음) $($it.Path)  — $($out -join ' ')" -ForegroundColor Yellow; $kept++ }
      }
      else {
        $age = if (Test-Path $it.Path) { ((Get-Date) - (Get-Item $it.Path).LastWriteTime).Days } else { 0 }
        $note = if ($age -ge $staleDays) { "미머지, ${age}일 방치 — 확인 후 수동 삭제" } else { '미머지' }
        Write-Host "  남김($note) $($it.Path)  [$($it.Branch)]" -ForegroundColor DarkYellow; $kept++
      }
    }
    Write-Host "  → 제거 $removed, 남김 $kept" -ForegroundColor Gray
  }
}
