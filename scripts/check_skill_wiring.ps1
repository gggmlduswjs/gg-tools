# 공통 스킬 설치·배선 확인 (읽기 전용)
# 사용: pwsh ./scripts/check_skill_wiring.ps1 [-BookmartPath <경로>] [-CoupangPath <경로>]
# 이 스크립트는 설치·삭제·설정 수정·DB 접근을 하지 않습니다.
param(
  [string]$BookmartPath,
  [string]$CoupangPath
)

$ErrorActionPreference = 'Stop'
$issues = 0
$claudeHome = Join-Path $HOME '.claude'
$registry = Join-Path $claudeHome 'plugins/installed_plugins.json'
$installed = $null

if (Test-Path $registry) {
  try { $installed = (Get-Content -LiteralPath $registry -Raw | ConvertFrom-Json).plugins }
  catch { Write-Warning "플러그인 등록정보 해석 실패: $($_.Exception.Message)"; $issues++ }
} else {
  Write-Warning "플러그인 등록정보가 없습니다: $registry"
  $issues++
}

Write-Host "== Claude Code 사용자 스코프 플러그인 ==" -ForegroundColor Cyan
$cfg = Get-Content -LiteralPath (Join-Path $PSScriptRoot '../plugins.json') -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($id in @($cfg.plugins | ForEach-Object { $_.id })) {
  $entry = if ($installed) { $installed.PSObject.Properties[$id] } else { $null }
  $scopes = @()
  if ($entry -and $entry.Value) { $scopes = @($entry.Value | ForEach-Object { $_.scope }) }
  if ($scopes -contains 'user') {
    Write-Host "  OK: $id (user)" -ForegroundColor Green
  } else {
    $issues++
    Write-Warning "설치 또는 user 범위 미확인: $id (발견 범위: $($scopes -join ','))"
  }
}

Write-Host "== 외부 단일 스킬 ==" -ForegroundColor Cyan
$grill = Join-Path $claudeHome 'skills/grill-me/SKILL.md'
if (Test-Path $grill) { Write-Host "  OK: grill-me 파일 존재" -ForegroundColor Green }
else { $issues++; Write-Warning "grill-me 누락: $grill" }

Write-Host "== 공통 Hook 엔진 ==" -ForegroundColor Cyan
$engine = Join-Path $HOME 'claude/gg-skills/hooks/guardrail.py'
if (Test-Path $engine) { Write-Host "  OK: 공통 guardrail 파일 존재" -ForegroundColor Green }
else { $issues++; Write-Warning "공통 guardrail 파일 누락: $engine" }

function Test-ProjectGuardrail([string]$Path, [string]$Label) {
  if (-not $Path) {
    Write-Host "  건너뜀: $Label 경로 미입력 — 해당 프로젝트 런타임 검증은 미수행" -ForegroundColor Yellow
    return
  }
  $guard = Join-Path $Path '.claude/hooks/guardrail.py'
  if (-not (Test-Path $guard)) {
    $script:issues++
    Write-Warning "$Label guardrail shim 누락: $guard"
    return
  }
  if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    $script:issues++
    Write-Warning "python을 찾을 수 없어 $Label selftest 미실행"
    return
  }
  & python $guard --selftest
  if ($LASTEXITCODE -ne 0) {
    $script:issues++
    Write-Warning "$Label guardrail selftest 실패: exit $LASTEXITCODE"
  } else {
    Write-Host "  OK: $Label guardrail selftest" -ForegroundColor Green
  }
}

Write-Host "== 프로젝트별 guardrail (경로 제공 시만) ==" -ForegroundColor Cyan
Test-ProjectGuardrail $BookmartPath 'Bookmart'
Test-ProjectGuardrail $CoupangPath 'Coupang_v2'

Write-Host "== 검증 범위 ==" -ForegroundColor Cyan
Write-Host "설치 등록·파일 존재 및 지정 프로젝트의 selftest만 확인했습니다."
Write-Host "스킬 자동 호출·Hook 실세션 이벤트·Codex 플러그인은 별도 세션 검증이 필요합니다."
if ($issues -gt 0) { Write-Warning "점검할 항목 $issues 건"; exit 1 }
Write-Host "정적 설치·배선 점검 통과 (실제 세션 호출까지 검증한 것은 아님)" -ForegroundColor Green
