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
    default { Write-Host "사용: dev bm|cp [이름]   (bm=bookmart, cp=Coupang_v2)" }
  }
}
