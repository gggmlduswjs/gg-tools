# gg-skills만 Codex에 설치. 외부 플러그인·인증·hook 신뢰 설정은 변경하지 않는다.
param([switch]$DryRun)
$ErrorActionPreference = 'Stop'

if ($DryRun) {
  Write-Host ('codex plugin marketplace add "{0}"' -f $PSScriptRoot)
  Write-Host 'codex plugin add gg-skills@gg-tools'
  Write-Host 'codex plugin list --json'
  exit 0
}
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
  throw 'Codex CLI가 필요합니다. 설치 후 새 PowerShell에서 다시 실행하세요.'
}
& codex plugin marketplace add $PSScriptRoot
if ($LASTEXITCODE -ne 0) { throw 'Codex marketplace 등록 실패' }
& codex plugin add 'gg-skills@gg-tools'
if ($LASTEXITCODE -ne 0) { throw 'gg-skills 설치 실패' }
& codex plugin list --json
if ($LASTEXITCODE -ne 0) { throw '설치 확인 실패' }
Write-Host '새 Codex 세션에서 스킬을 확인하세요. hook은 정의를 검토하고 직접 신뢰해야 활성화됩니다.'
