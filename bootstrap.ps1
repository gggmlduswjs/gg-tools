# bootstrap.ps1 — gg-tools 한 번 실행으로 Claude Code 개발 환경을 설치/업데이트한다.
#
# 설치 목록은 plugins.json 한 파일이다(플러그인, 단일 스킬, 세컨드 브레인 clone, npm 도구).
# 멱등 실행: 이미 있으면 update, 없으면 install. core 플러그인 실패는 중단, 나머지는 경고만.
# -DryRun: 아무것도 바꾸지 않고 실행할 명령만 출력한다.
param([switch]$DryRun)

$ErrorActionPreference = 'Stop'
$cfg = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'plugins.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$dotClaude = Join-Path $env:USERPROFILE '.claude'
$warnings = New-Object System.Collections.Generic.List[string]

function Invoke-Claude {
  param([Parameter(Mandatory=$true)][string[]]$CliArgs)
  if ($DryRun) { Write-Host "    [dry] claude $($CliArgs -join ' ')" -Fore DarkGray; return $true }
  # Out-Host 필수: stdout 이 반환값에 섞이면 호출부의 if 가 실패를 성공으로 읽는다.
  & claude @CliArgs | Out-Host
  return ($LASTEXITCODE -eq 0)
}

function Ensure-Marketplace {
  param($Mp)
  Write-Host "  marketplace $($Mp.name)" -Fore DarkCyan
  if (Invoke-Claude @('plugin','marketplace','update',$Mp.name)) { return $true }
  return (Invoke-Claude @('plugin','marketplace','add',$Mp.repo,'--scope','user'))
}

function Ensure-Plugin {
  param([string]$Id)
  Write-Host "  $Id" -Fore DarkCyan
  if (Invoke-Claude @('plugin','update',$Id,'--scope','user')) { return $true }
  return (Invoke-Claude @('plugin','install',$Id,'--scope','user'))
}

if (-not $DryRun -and -not (Get-Command claude -ErrorAction SilentlyContinue)) {
  throw "Claude Code 명령 'claude'를 찾을 수 없다. Claude Code를 먼저 설치한 뒤 새 PowerShell 창에서 다시 실행해라."
}

# 일부 플러그인은 소스를 SSH 주소(git@github.com:)로 선언한다. SSH 키가 없는 새 PC 에서는
# 설치가 실패하므로, HTTPS(gh 로그인)로 바꿔 받게 한다. 이미 있으면 건너뛴다.
if (-not $DryRun -and -not (git config --global --get-all url.https://github.com/.insteadOf)) {
  git config --global url."https://github.com/".insteadOf "git@github.com:"
}

Write-Host "`n== 마켓플레이스 ==" -Fore Cyan
$failedMp = @{}
foreach ($mp in $cfg.marketplaces) {
  if (-not (Ensure-Marketplace $mp)) { $failedMp[$mp.name] = $true; $warnings.Add("marketplace 실패: $($mp.name) ($($mp.repo))") }
}

Write-Host "`n== 플러그인 ==" -Fore Cyan
foreach ($pl in $cfg.plugins) {
  $mpName = ($pl.id -split '@')[1]
  $ok = (-not $failedMp.ContainsKey($mpName)) -and (Ensure-Plugin $pl.id)
  if ($ok) { continue }
  if ($pl.core) { throw "필수 플러그인 설치 실패: $($pl.id). GitHub 로그인(gh auth status)과 네트워크를 확인해라." }
  $warnings.Add("플러그인 실패: $($pl.id)")
}

Write-Host "`n== 단일 스킬 ==" -Fore Cyan
foreach ($sk in $cfg.skills) {
  $dir = Join-Path $dotClaude "skills\$($sk.name)"
  Write-Host "  $($sk.name) -> $dir" -Fore DarkCyan
  if ($DryRun) { continue }
  try {
    New-Item -ItemType Directory -Force $dir | Out-Null
    Invoke-WebRequest -Uri $sk.url -OutFile (Join-Path $dir 'SKILL.md') -UseBasicParsing
  } catch { $warnings.Add("스킬 실패: $($sk.name) ($($_.Exception.Message))") }
}

Write-Host "`n== 스킬 저장소 ==" -Fore Cyan
foreach ($sr in $cfg.skillRepos) {
  $dir = Join-Path $dotClaude "skills\$($sr.name)"
  Write-Host "  $($sr.name) <- $($sr.repo)" -Fore DarkCyan
  if ($DryRun) { continue }
  try {
    if (Test-Path (Join-Path $dir '.git')) { git -C $dir pull --ff-only 2>&1 | Out-Host }
    else { gh repo clone $sr.repo $dir 2>&1 | Out-Host }
    if ($LASTEXITCODE -ne 0) { throw "git/gh 종료코드 $LASTEXITCODE" }
  } catch { $warnings.Add("스킬 저장소 실패: $($sr.repo) ($($_.Exception.Message))") }
}

Write-Host "`n== 저장소 ==" -Fore Cyan
foreach ($r in $cfg.repos) {
  $dir = Join-Path $env:USERPROFILE $r.dir
  Write-Host "  $($r.repo) -> $dir" -Fore DarkCyan
  if ($DryRun) { continue }
  if (Test-Path (Join-Path $dir '.git')) { Write-Host '    [ok] 이미 있음' -Fore Green; continue }
  gh repo clone $r.repo $dir 2>&1 | Out-Host
  if ($LASTEXITCODE -ne 0) { $warnings.Add("저장소 clone 실패: $($r.repo) — gh auth login 후 다시 실행") }
}

Write-Host "`n== npm 전역 도구 ==" -Fore Cyan
foreach ($pkg in $cfg.npmGlobal) {
  Write-Host "  $pkg" -Fore DarkCyan
  if ($DryRun) { continue }
  if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { $warnings.Add("npm 없음: $pkg 건너뜀 (winget install --id OpenJS.NodeJS.LTS -e)"); continue }
  npm install -g $pkg 2>&1 | Out-Host
  if ($LASTEXITCODE -ne 0) { $warnings.Add("npm 설치 실패: $pkg") }
}

# 여러 스킬이 든 저장소: ~\.claude\external\<이름> 에 받고, SKILL.md 가 있는 폴더마다
# ~\.claude\skills\<스킬> 로 junction(관리자 권한 불필요)을 건다. 같은 이름이 이미 있으면 건드리지 않는다.
Write-Host "`n== 스킬 모음 ==" -Fore Cyan
foreach ($c in $cfg.skillCollections) {
  $src = Join-Path $dotClaude "external\$($c.name)"
  Write-Host "  $($c.repo) -> $src" -Fore DarkCyan
  if ($DryRun) { continue }
  try {
    if (Test-Path (Join-Path $src '.git')) { git -C $src pull --ff-only 2>&1 | Out-Host }
    else { New-Item -ItemType Directory -Force (Split-Path $src) | Out-Null; gh repo clone $c.repo $src 2>&1 | Out-Host }
    if ($LASTEXITCODE -ne 0) { throw "git/gh 종료코드 $LASTEXITCODE" }
    New-Item -ItemType Directory -Force (Join-Path $dotClaude 'skills') | Out-Null
    foreach ($d in Get-ChildItem -LiteralPath $src -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'SKILL.md') }) {
      $link = Join-Path $dotClaude "skills\$($d.Name)"
      if (Test-Path $link) {
        if (-not ((Get-Item $link -Force).LinkType)) { $warnings.Add("같은 이름의 스킬이 이미 있어 건너뜀: $($d.Name)") }
        continue
      }
      New-Item -ItemType Junction -Path $link -Target $d.FullName | Out-Null
      Write-Host "    [ok] $($d.Name)" -Fore Green
    }
  } catch { $warnings.Add("스킬 모음 실패: $($c.repo) ($($_.Exception.Message))") }
}

# 상태줄: 이미 설정돼 있으면 건드리지 않는다. 없을 때만 넣고 원본은 .bak 으로 남긴다.
Write-Host "`n== 상태줄 ==" -Fore Cyan
$settingsPath = Join-Path $dotClaude 'settings.json'
if ($cfg.statusLine -and -not $DryRun) {
  try {
    $st = if (Test-Path $settingsPath) { Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json } else { [pscustomobject]@{} }
    if ($st.PSObject.Properties['statusLine']) { Write-Host '  이미 설정돼 있어 그대로 둔다.' -Fore Green }
    else {
      if (Test-Path $settingsPath) { Copy-Item -LiteralPath $settingsPath "$settingsPath.bak" -Force }
      $st | Add-Member -NotePropertyName statusLine -NotePropertyValue $cfg.statusLine
      $st | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $settingsPath -Encoding UTF8
      Write-Host '  ccstatusline 설정 완료' -Fore Green
    }
  } catch { $warnings.Add("상태줄 설정 실패: $($_.Exception.Message)") }
}

Write-Host "`n== 완료 ==" -Fore Cyan
foreach ($o in $cfg.optionalPlugins) { Write-Host "  선택 설치: $($o.id) — $($o.note)" -Fore DarkGray }
if ($warnings.Count -gt 0) {
  Write-Host "`n경고 $($warnings.Count)건:" -Fore Yellow
  $warnings | ForEach-Object { Write-Host "  - $_" -Fore Yellow }
  Write-Host '다시 실행해도 안전하다(이미 된 것은 건너뛴다).' -Fore DarkGray
} else {
  Write-Host '모두 최신 상태다.' -Fore Green
}
Write-Host '열려 있는 Claude Code 세션은 /reload-plugins 또는 새 세션에서 반영된다.' -Fore DarkGray
