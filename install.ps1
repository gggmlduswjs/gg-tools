# install.ps1 — 이 PC에 dotfiles 를 배선(idempotent). 프로필 dev 런처 + ~\.claude 설정.
#   새 PC: git clone <이 레포> ~\dotfiles ;  pwsh ~\dotfiles\install.ps1 ;  새 터미널
#   -Force = 이미 있는 ~\.claude 파일도 덮어씀(기본은 안 건드림 — 그 PC 설정을 날리지 않는다)
param([switch]$Force)
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

# ── ~\.claude 손으로 쓴 설정 ──────────────────────────────────────────────
# 여기 없으면 이 PC 디스크가 죽을 때 같이 사라진다(CLAUDE.md = Claude 에게 주는 전역 지침).
# 기본은 **없는 것만** 채운다 — 그 PC에서 따로 손본 설정을 조용히 덮으면 안 된다.
$claudeSrc = Join-Path $PSScriptRoot 'claude'
$claudeDst = Join-Path $env:USERPROFILE '.claude'
if (Test-Path $claudeSrc) {
  foreach ($f in (Get-ChildItem $claudeSrc -Recurse -File)) {
    $rel  = $f.FullName.Substring($claudeSrc.Length).TrimStart('\')
    $dest = Join-Path $claudeDst $rel
    if ((Test-Path $dest) -and -not $Force) { Write-Host "  이미 있음 — 건너뜀: $rel"; continue }
    New-Item -ItemType Directory -Force (Split-Path $dest -Parent) | Out-Null
    Copy-Item $f.FullName $dest -Force
    Write-Host "  배치: $rel"
  }
}
