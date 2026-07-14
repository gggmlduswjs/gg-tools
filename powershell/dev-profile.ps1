# dev-profile.ps1 — 프로젝트 세션 격리 통일 런처 (dotfiles).
# PowerShell 프로필에서 dot-source 해서 쓴다 (install.ps1이 자동 배선).
#
#   dev bm 반품   → bookmart 격리 worktree에서 claude 자동 시작
#   dev cp 광고   → Coupang_v2 격리 worktree에서 claude 자동 시작
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
    default { Write-Host "사용: dev bm|cp [이름]   (bm=bookmart, cp=Coupang_v2)   |   devr = 세션 이어하기" }
  }
}

function devr {
  # 모든 bookmart/Coupang 세션(메인+워크트리)을 한 목록에서 골라 resume.
  # --resume은 현재 폴더 세션만 보여줘서, 워크트리 세션을 메인에서 못 봄 → 이걸로 통합.
  param([int]$top = 20)
  $root = Join-Path $env:USERPROFILE '.claude\projects'
  $rows = foreach ($d in Get-ChildItem $root -Directory | Where-Object Name -match 'bookmart|Coupang') {
    foreach ($f in Get-ChildItem $d.FullName -Filter *.jsonl -File) {
      $sid = $cwd = $title = $null
      foreach ($line in [System.IO.File]::ReadLines($f.FullName)) {   # 지연 읽기 — 필드 찾으면 즉시 중단
        if ($line -notmatch '"(cwd|sessionId|summary)"') { continue }
        try { $o = $line | ConvertFrom-Json } catch { continue }
        if (-not $sid   -and $o.sessionId)          { $sid   = $o.sessionId }
        if (-not $cwd   -and $o.cwd)                { $cwd   = $o.cwd }
        if (-not $title -and $o.type -eq 'summary') { $title = $o.summary }
        if ($sid -and $cwd -and $title) { break }
      }
      if ($sid -and $cwd) {
        [pscustomobject]@{ Time = $f.LastWriteTime; Cwd = $cwd; Sid = $sid
          Title = ($title ?? (Split-Path $cwd -Leaf)) }
      }
    }
  }
  $rows = @($rows | Sort-Object Time -Descending | Select-Object -First $top)
  if (-not $rows) { Write-Warning '세션 없음'; return }
  for ($i = 0; $i -lt $rows.Count; $i++) {
    $r = $rows[$i]
    '{0,2}  {1:MM-dd HH:mm}  {2,-22}  {3}' -f ($i + 1), $r.Time, (Split-Path $r.Cwd -Leaf), $r.Title
  }
  $pick = Read-Host "`n번호 (취소=Enter)"
  if (-not $pick) { return }
  $sel = $rows[[int]$pick - 1]
  if (-not $sel) { Write-Warning '범위 밖 번호'; return }
  if (-not (Test-Path $sel.Cwd)) { Write-Warning "폴더 없음(워크트리 삭제됨?): $($sel.Cwd)"; return }
  Set-Location $sel.Cwd
  claude --resume $sel.Sid
}
