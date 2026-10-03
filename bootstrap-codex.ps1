# gg-skills만 Codex에 설치. 외부 플러그인·인증·hook 신뢰 설정은 변경하지 않는다.
param([switch]$DryRun, [string]$CodexExecutable)
$ErrorActionPreference = 'Stop'

function Resolve-CodexExecutable {
  if ($CodexExecutable) {
    if (-not (Test-Path -LiteralPath $CodexExecutable -PathType Leaf)) {
      throw 'Specified CodexExecutable does not exist.'
    }
    return (Resolve-Path -LiteralPath $CodexExecutable).ProviderPath
  }
  # Windows: npm launcher와 desktop 동봉본의 캐시 활성화 동작이 다를 수 있다.
  if ($env:LOCALAPPDATA) {
    $desktopRoot = Join-Path $env:LOCALAPPDATA 'OpenAI/Codex/bin'
    if (Test-Path -LiteralPath $desktopRoot -PathType Container) {
      $running = @(Get-Process -Name codex -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path.StartsWith($desktopRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) } |
        Sort-Object StartTime -Descending | Select-Object -ExpandProperty Path -Unique)
      if ($running.Count -gt 0) { return $running[0] }
      $bundled = @(Get-ChildItem -LiteralPath $desktopRoot -Directory | ForEach-Object {
        $candidate = Join-Path $_.FullName 'codex.exe'
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { Get-Item -LiteralPath $candidate }
      } | Sort-Object LastWriteTime -Descending)
      if ($bundled.Count -gt 0) { return $bundled[0].FullName }
    }
  }
  $fromPath = Get-Command codex -ErrorAction SilentlyContinue
  if ($fromPath) { return $fromPath.Source }
  if ($DryRun) { return 'codex' }
  throw 'Codex CLI is required. Install it and reopen PowerShell.'
}

$cliPath = Resolve-CodexExecutable
Write-Host ('Codex executable: {0}' -f $cliPath)
if ($DryRun) {
  Write-Host ('& "{0}" plugin marketplace add "{1}"' -f $cliPath, $PSScriptRoot)
  Write-Host ('& "{0}" plugin add gg-skills@gg-tools' -f $cliPath)
  Write-Host ('& "{0}" plugin list --json' -f $cliPath)
  exit 0
}
& $cliPath plugin marketplace add $PSScriptRoot
if ($LASTEXITCODE -ne 0) { throw 'Codex marketplace registration failed.' }
& $cliPath plugin add 'gg-skills@gg-tools'
if ($LASTEXITCODE -ne 0) { throw 'gg-skills installation failed.' }
$pluginReportRaw = & $cliPath plugin list --json
if ($LASTEXITCODE -ne 0) { throw 'Plugin installation verification failed.' }
$pluginReport = ($pluginReportRaw -join [Environment]::NewLine) | ConvertFrom-Json
$installed = @($pluginReport.installed | Where-Object { $_.pluginId -eq 'gg-skills@gg-tools' })
if ($installed.Count -ne 1 -or -not $installed[0].installed -or -not $installed[0].enabled) {
  throw 'gg-skills must be installed and enabled.'
}
$installed[0] | Select-Object pluginId,version,installed,enabled | ConvertTo-Json
Write-Host 'Open a new Codex session to use the skills. Review and trust hooks in /hooks before enabling them.'
