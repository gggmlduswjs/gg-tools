# install.ps1 — 이 PC의 PowerShell 프로필에 dotfiles dev 런처를 배선(idempotent).
#   새 PC: git clone <이 레포> ~\dotfiles ;  pwsh ~\dotfiles\install.ps1 ;  새 터미널
$ErrorActionPreference = 'Stop'
$dev    = Join-Path $PSScriptRoot 'powershell\dev-profile.ps1'
$marker = '# >>> dotfiles dev launcher >>>'

if (-not (Test-Path $dev)) { throw "본체 없음: $dev (레포 clone 확인)" }
$dir = Split-Path $PROFILE -Parent
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
if (-not (Test-Path $PROFILE)) { New-Item -ItemType File -Force $PROFILE | Out-Null }

$content = Get-Content $PROFILE -Raw -ErrorAction SilentlyContinue
if ($content -and $content.Contains($marker)) {
  Write-Host "이미 배선됨 — 건너뜀 ($PROFILE)"
}
else {
  Add-Content $PROFILE "`n$marker`n. `"$dev`"`n# <<< dotfiles dev launcher <<<`n"
  Write-Host "배선 완료 → $PROFILE"
  Write-Host "새 터미널을 열면 'dev bm 반품' / 'dev cp 광고' 사용 가능"
}
