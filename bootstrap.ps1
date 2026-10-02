# bootstrap.ps1 — gg-tools 한 번 실행으로 공용 Claude Code 환경을 설치/업데이트한다.
#
# 설치/업데이트 대상:
#   1) Superpowers (Anthropic 공식 marketplace)
#   2) gg-skills (이 repo의 gg-tools marketplace)
#   3) RobMitt/grill-me-skill (원본 SKILL.md)
#
# 멱등 실행을 목표로 한다. 이미 있으면 update, 없으면 install 한다.
param()

$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot
$dotClaude = Join-Path $env:USERPROFILE '.claude'

function Invoke-ClaudePlugin {
  param(
    [Parameter(Mandatory=$true)][string[]]$Args,
    [switch]$AllowFailure
  )

  # Out-Host 필수: `& claude @Args` 의 stdout 이 파이프라인에 남으면 함수 반환값이
  # [출력줄..., $false] 배열이 되고, PowerShell 은 비어있지 않은 배열을 항상 참으로 본다.
  # 그러면 호출부의 `if ($updated)` 가 실패를 성공으로 읽어 install 을 통째로 건너뛴다.
  & claude @Args | Out-Host
  $code = $LASTEXITCODE
  if ($code -ne 0 -and -not $AllowFailure) {
    throw "claude $($Args -join ' ') 실패 (exit $code)"
  }
  return ($code -eq 0)
}

function Ensure-Plugin {
  param([Parameter(Mandatory=$true)][string]$PluginId)

  Write-Host "  $PluginId" -Fore DarkCyan
  $updated = Invoke-ClaudePlugin -Args @('plugin','update',$PluginId,'--scope','user') -AllowFailure
  if ($updated) {
    Write-Host "    [ok] 최신화" -Fore Green
    return
  }

  Invoke-ClaudePlugin -Args @('plugin','install',$PluginId,'--scope','user') | Out-Null
  Write-Host "    [ok] 설치" -Fore Green
}

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  throw "Claude Code 명령 'claude'를 찾을 수 없다. Claude Code를 먼저 설치한 뒤 다시 실행해라."
}

Write-Host "`n== Claude Code plugins ==" -Fore Cyan

# 1) Superpowers — 공식 Claude marketplace 정본.
Ensure-Plugin 'superpowers@claude-plugins-official'

# 2) gg-tools marketplace → gg-skills.
#    2026-09-01 에 repo 를 claude→gg-tools 로 rename 했다. 옛 이름은 GitHub 리다이렉트로
#    아직 붙지만, 옛 클론이 남은 PC 를 위해 fallback 을 남겨 둔다.
$marketReady = Invoke-ClaudePlugin -Args @('plugin','marketplace','update','gg-tools') -AllowFailure
if (-not $marketReady) {
  # 옛 marketplace를 제거하면 그 marketplace에서 설치했던 legacy gg-harness도 같이 정리된다.
  Invoke-ClaudePlugin -Args @('plugin','marketplace','remove','gg-harness') -AllowFailure | Out-Null

  $marketReady = Invoke-ClaudePlugin -Args @('plugin','marketplace','add','gggmlduswjs/gg-tools','--scope','user') -AllowFailure
  if (-not $marketReady) {
    # 옛 이름 — GitHub 리다이렉트. 2026-09-01 rename 전 클론이 남은 PC 용 fallback.
    $marketReady = Invoke-ClaudePlugin -Args @('plugin','marketplace','add','gggmlduswjs/claude','--scope','user') -AllowFailure
  }
  if (-not $marketReady) {
    throw 'gg-tools marketplace 추가 실패. GitHub 인증/네트워크와 repo 이름을 확인해라.'
  }
}
Ensure-Plugin 'gg-skills@gg-tools'

# 2.5) mattpocock-skills — 업스트림 정본.
#      gg-skills 는 domain-modeling·grilling 을 여기서 복사해 갖고 있었고 업스트림이
#      갱신되는 동안 사본이 낡았다(2026-08-30: grilling 10줄 vs 업스트림 28줄).
#      사본을 지웠으니 이 플러그인이 없으면 두 스킬을 잃는다 — 설치는 선택이 아니다.
$mpReady = Invoke-ClaudePlugin -Args @('plugin','marketplace','update','mattpocock') -AllowFailure
if (-not $mpReady) {
  $mpReady = Invoke-ClaudePlugin -Args @('plugin','marketplace','add','mattpocock/skills','--scope','user') -AllowFailure
  if (-not $mpReady) {
    throw 'mattpocock marketplace 추가 실패. GitHub 인증/네트워크를 확인해라.'
  }
}
Ensure-Plugin 'mattpocock-skills@mattpocock'

# 3) grill-me — RobMitt 원본은 marketplace plugin이 아니라 단일 Claude skill이다.
Write-Host "`n== grill-me ==" -Fore Cyan
$grillDir = Join-Path $dotClaude 'skills\grill-me'
$grillFile = Join-Path $grillDir 'SKILL.md'
New-Item -ItemType Directory -Force $grillDir | Out-Null
$grillUrl = 'https://raw.githubusercontent.com/RobMitt/grill-me-skill/main/SKILL.md'
try {
  Invoke-WebRequest -Uri $grillUrl -OutFile $grillFile -UseBasicParsing
  Write-Host "  [ok] RobMitt/grill-me-skill 최신 원본 → $grillFile" -Fore Green
} catch {
  throw "grill-me 동기화 실패: $($_.Exception.Message)"
}

Write-Host "`n== 완료 ==" -Fore Cyan
Write-Host 'Superpowers + gg-skills + grill-me 가 최신 상태다.' -Fore Green
Write-Host '열려 있는 Claude Code 세션은 /reload-plugins 또는 새 세션에서 최신 plugin을 사용한다.' -Fore DarkGray
