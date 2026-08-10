#!/usr/bin/env pwsh
# relocate-projects.ps1 — Desktop 바로 아래 프로젝트들을 묶음 폴더로 옮긴다.
#
# 기본은 dry-run. 실제 적용은 Codex/Claude/VS Code 등 bookmart/Coupang 폴더를 잡은 창을
# 모두 닫고, 중립 위치(예: Desktop)에서 아래처럼 실행한다:
#
#   pwsh C:\Users\user\claude\powershell\relocate-projects.ps1 -Apply
#
# 하는 일:
#   1. Desktop\bookmart              -> Desktop\북마트\bookmart
#   2. Desktop\bookmart-wt           -> Desktop\북마트\bookmart-wt
#   3. Desktop\Coupang_v2            -> Desktop\쿠팡\Coupang_v2
#   4. Desktop\Coupang_v2-wt         -> Desktop\쿠팡\Coupang_v2-wt
#   5. git worktree repair
#   6. git safe.directory 새 경로 갱신
#   7. .codex/config.toml, .claude/settings.json, dev-profile.ps1 경로 치환

[CmdletBinding()]
param(
  [switch] $Apply,
  [ValidateSet('All', 'Bookmart', 'Coupang')]
  [string] $Project = 'All'
)

$ErrorActionPreference = 'Stop'

function FullPath([string]$Path) {
  return [System.IO.Path]::GetFullPath($Path)
}

function GitPath([string]$Path) {
  return (FullPath $Path).Replace('\', '/')
}

function Assert-Under([string]$Path, [string]$Root) {
  $full = FullPath $Path
  $base = (FullPath $Root).TrimEnd('\') + '\'
  if (-not $full.StartsWith($base, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "대상 경로가 컨테이너 밖이다: $full (container: $base)"
  }
}

function Invoke-Step([string]$Message, [scriptblock]$Action) {
  if ($Apply) {
    Write-Host "DO   $Message" -ForegroundColor Green
    & $Action
  }
  else {
    Write-Host "DRY  $Message" -ForegroundColor DarkGray
  }
}

function Get-WorktreePaths([string]$Repo) {
  if (-not (Test-Path -LiteralPath $Repo)) { return @() }
  return @(& git -C $Repo worktree list --porcelain |
    Where-Object { $_ -like 'worktree *' } |
    ForEach-Object { $_.Substring(9) })
}

function Add-SafeDirectory([string]$Path) {
  $p = GitPath $Path
  $existing = @(git config --global --get-all safe.directory 2>$null)
  if ($existing -notcontains $p) {
    Invoke-Step "git safe.directory add $p" { git config --global --add safe.directory $p }
  }
}

function Remove-SafeDirectory([string]$Path) {
  $p = GitPath $Path
  $existing = @(git config --global --get-all safe.directory 2>$null)
  if ($existing -contains $p) {
    Invoke-Step "git safe.directory remove $p" { git config --global --unset-all safe.directory $p 2>$null; $global:LASTEXITCODE = 0 }
  }
}

function Move-ProjectDir([string]$Name, [string]$Source, [string]$Dest, [string]$Container) {
  Assert-Under $Dest $Container
  $srcExists = Test-Path -LiteralPath $Source
  $dstExists = Test-Path -LiteralPath $Dest
  if ($srcExists -and $dstExists) { throw "대상과 원본이 둘 다 있다: $Source / $Dest" }
  if ($srcExists) {
    Invoke-Step "move $Name`: $Source -> $Dest" {
      try {
        Move-Item -LiteralPath $Source -Destination $Dest
      }
      catch {
        $hint = @(
          "폴더가 사용 중이라 이동 실패: $Source",
          "닫을 것: 해당 폴더를 연 Codex task, Claude, VS Code, PowerShell/터미널, runserver/test 프로세스",
          "Bookmart가 현재 Codex workspace라면 이 Codex task 자체를 닫아야 이동된다.",
          "Coupang만 먼저 옮기려면: pwsh C:\Users\user\claude\powershell\relocate-projects.ps1 -Apply -Project Coupang"
        )
        throw (($hint -join "`n") + "`n원본 오류: $($_.Exception.Message)")
      }
    }
  }
  elseif ($dstExists) {
    Write-Host "OK   already moved $Name`: $Dest" -ForegroundColor DarkGreen
  }
  else {
    Write-Warning "원본/대상 모두 없음: $Name ($Source / $Dest)"
  }
}

function Repair-Worktrees([string]$Main, [string]$WtRoot) {
  if (-not (Test-Path -LiteralPath $Main)) { return }
  if (-not (Test-Path -LiteralPath $WtRoot)) { return }
  $wtDirs = @(Get-ChildItem -Directory -LiteralPath $WtRoot |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName '.git') } |
    ForEach-Object { $_.FullName })
  if ($wtDirs.Count -eq 0) { return }
  Invoke-Step "git worktree repair ($Main)" {
    & git -C $Main worktree repair @wtDirs
    if ($LASTEXITCODE -ne 0) { throw "git worktree repair 실패: $Main" }
  }
}

function Replace-InFile([string]$Path, [array]$Pairs) {
  if (-not (Test-Path -LiteralPath $Path)) { return }
  $utf8 = [System.Text.UTF8Encoding]::new($false)
  $resolved = (Resolve-Path -LiteralPath $Path).Path
  $text = [System.IO.File]::ReadAllText($resolved, $utf8)
  $next = $text
  foreach ($pair in $Pairs) {
    $next = $next.Replace($pair.From, $pair.To)
  }
  if ($next -eq $text) { return }
  Invoke-Step "update config paths: $resolved" {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    Copy-Item -LiteralPath $resolved -Destination "$resolved.bak-relocate-$stamp" -Force
    [System.IO.File]::WriteAllText($resolved, $next, $utf8)
  }
}

$desktop = Join-Path $env:USERPROFILE 'Desktop'
$bmContainer = Join-Path $desktop '북마트'
$cpContainer = Join-Path $desktop '쿠팡'

$oldBmMain = Join-Path $desktop 'bookmart'
$oldBmWt = Join-Path $desktop 'bookmart-wt'
$oldCpMain = Join-Path $desktop 'Coupang_v2'
$oldCpWt = Join-Path $desktop 'Coupang_v2-wt'

$newBmMain = Join-Path $bmContainer 'bookmart'
$newBmWt = Join-Path $bmContainer 'bookmart-wt'
$newCpMain = Join-Path $cpContainer 'Coupang_v2'
$newCpWt = Join-Path $cpContainer 'Coupang_v2-wt'

Write-Host "Mode: $(if ($Apply) { 'APPLY' } else { 'DRY RUN' })"
Write-Host "Project: $Project"
Write-Host "Bookmart: $oldBmMain -> $newBmMain"
Write-Host "Coupang : $oldCpMain -> $newCpMain"
Write-Host ""

$doBookmart = $Project -in @('All', 'Bookmart')
$doCoupang = $Project -in @('All', 'Coupang')

$oldSafe = @()
if ($doBookmart) { $oldSafe += @($oldBmMain, $oldBmWt) + (Get-WorktreePaths $oldBmMain) }
if ($doCoupang) { $oldSafe += @($oldCpMain, $oldCpWt) + (Get-WorktreePaths $oldCpMain) }

Invoke-Step "ensure container $bmContainer" { New-Item -ItemType Directory -Force -Path $bmContainer | Out-Null }
Invoke-Step "ensure container $cpContainer" { New-Item -ItemType Directory -Force -Path $cpContainer | Out-Null }

if ($doBookmart) {
  Move-ProjectDir 'bookmart' $oldBmMain $newBmMain $bmContainer
  Move-ProjectDir 'bookmart-wt' $oldBmWt $newBmWt $bmContainer
}
if ($doCoupang) {
  Move-ProjectDir 'Coupang_v2' $oldCpMain $newCpMain $cpContainer
  Move-ProjectDir 'Coupang_v2-wt' $oldCpWt $newCpWt $cpContainer
}

if ($doBookmart) { Repair-Worktrees $newBmMain $newBmWt }
if ($doCoupang) { Repair-Worktrees $newCpMain $newCpWt }

foreach ($p in ($oldSafe | Where-Object { $_ } | ForEach-Object { GitPath $_ } | Select-Object -Unique)) {
  Remove-SafeDirectory $p
}

$newSafe = @()
if ($doBookmart) { $newSafe += @($newBmMain) + (Get-WorktreePaths $newBmMain) }
if ($doCoupang) { $newSafe += @($newCpMain) + (Get-WorktreePaths $newCpMain) }
foreach ($p in ($newSafe | Where-Object { $_ } | ForEach-Object { GitPath $_ } | Select-Object -Unique)) {
  Add-SafeDirectory $p
}

$bookmartPathPairs = @(
  [pscustomobject]@{ From = '$HOME\Desktop\bookmart-wt'; To = '$HOME\Desktop\북마트\bookmart-wt' },
  [pscustomobject]@{ From = '$HOME\Desktop\bookmart'; To = '$HOME\Desktop\북마트\bookmart' },
  [pscustomobject]@{ From = 'C:\Users\user\Desktop\bookmart-wt'; To = 'C:\Users\user\Desktop\북마트\bookmart-wt' },
  [pscustomobject]@{ From = 'C:/Users/user/Desktop/bookmart-wt'; To = 'C:/Users/user/Desktop/북마트/bookmart-wt' },
  [pscustomobject]@{ From = 'C:\Users\user\Desktop\bookmart'; To = 'C:\Users\user\Desktop\북마트\bookmart' },
  [pscustomobject]@{ From = 'C:/Users/user/Desktop/bookmart'; To = 'C:/Users/user/Desktop/북마트/bookmart' },
  [pscustomobject]@{ From = 'c:\users\user\desktop\bookmart-wt'; To = 'c:\users\user\desktop\북마트\bookmart-wt' },
  [pscustomobject]@{ From = 'c:\users\user\desktop\bookmart'; To = 'c:\users\user\desktop\북마트\bookmart' }
)

$coupangPathPairs = @(
  [pscustomobject]@{ From = '$HOME\Desktop\Coupang_v2-wt'; To = '$HOME\Desktop\쿠팡\Coupang_v2-wt' },
  [pscustomobject]@{ From = '$HOME\Desktop\Coupang_v2'; To = '$HOME\Desktop\쿠팡\Coupang_v2' },
  [pscustomobject]@{ From = 'C:\Users\user\Desktop\Coupang_v2-wt'; To = 'C:\Users\user\Desktop\쿠팡\Coupang_v2-wt' },
  [pscustomobject]@{ From = 'C:/Users/user/Desktop/Coupang_v2-wt'; To = 'C:/Users/user/Desktop/쿠팡/Coupang_v2-wt' },
  [pscustomobject]@{ From = 'C:\Users\user\Desktop\Coupang_v2'; To = 'C:\Users\user\Desktop\쿠팡\Coupang_v2' },
  [pscustomobject]@{ From = 'C:/Users/user/Desktop/Coupang_v2'; To = 'C:/Users/user/Desktop/쿠팡/Coupang_v2' },
  [pscustomobject]@{ From = 'c:\users\user\desktop\coupang_v2-wt'; To = 'c:\users\user\desktop\쿠팡\coupang_v2-wt' },
  [pscustomobject]@{ From = 'c:\users\user\desktop\coupang_v2'; To = 'c:\users\user\desktop\쿠팡\coupang_v2' }
)

$pathPairs = @()
if ($doBookmart) { $pathPairs += $bookmartPathPairs }
if ($doCoupang) { $pathPairs += $coupangPathPairs }

Replace-InFile (Join-Path $env:USERPROFILE '.codex\config.toml') $pathPairs
Replace-InFile (Join-Path $env:USERPROFILE '.claude\settings.json') $pathPairs
Replace-InFile (Join-Path $env:USERPROFILE 'claude\powershell\dev-profile.ps1') $pathPairs
Replace-InFile (Join-Path $env:USERPROFILE 'Documents\PowerShell\profile.ps1') $pathPairs
Replace-InFile (Join-Path $env:USERPROFILE 'Documents\PowerShell\Microsoft.PowerShell_profile.ps1') $pathPairs
Replace-InFile (Join-Path $env:USERPROFILE 'Documents\WindowsPowerShell\profile.ps1') $pathPairs
Replace-InFile (Join-Path $env:USERPROFILE 'Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1') $pathPairs

Write-Host ""
if ($Apply) {
  Write-Host "완료. 새 터미널에서 dev bm / dev cp 를 확인하세요." -ForegroundColor Green
}
else {
  Write-Host "DRY RUN 완료. 실제 적용은 -Apply 를 붙여 실행합니다." -ForegroundColor Green
}
