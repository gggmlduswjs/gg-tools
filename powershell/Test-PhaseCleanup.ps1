#!/usr/bin/env pwsh
# Harness phase cleanup check.
# Verifies that cleanup archives completed phases only, keeps active/unresolved
# phases in place, and prunes only archived phases from phases/index.json.
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "ai-engine.ps1")

function Assert {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw "FAIL: $Message" }
    Write-Host "  ok: $Message"
}

function Write-JsonFile {
    param([string] $Path, $Value)
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Path) | Out-Null
    $Value | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function New-TestPhase {
    param(
        [string] $RootPath,
        [string] $Name,
        [string[]] $Statuses,
        [string] $CompletedAt = ""
    )

    $phaseDir = Join-Path $RootPath ".dev\harness\phases\$Name"
    New-Item -ItemType Directory -Force -Path $phaseDir | Out-Null
    $steps = @()
    for ($i = 0; $i -lt $Statuses.Count; $i++) {
        $steps += [pscustomobject]@{ step = $i; name = "step-$i"; status = $Statuses[$i] }
    }
    $index = [ordered]@{
        project = "test"
        phase = $Name
        source_plan = ".dev/plans/be/$($Name)_plan.md"
        steps = $steps
    }
    if ($CompletedAt) { $index.completed_at = $CompletedAt }
    $indexPath = Join-Path $phaseDir "index.json"
    Write-JsonFile $indexPath $index
    (Get-Item -LiteralPath $indexPath).LastWriteTime = (Get-Date).AddDays(-2)
}

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("phase-cleanup-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
$root = Join-Path $tmp "repo"

try {
    New-Item -ItemType Directory -Force -Path $root | Out-Null
    & git -C $root init -q --initial-branch=main
    if ($LASTEXITCODE -ne 0) { throw "git init failed" }

    New-TestPhase -RootPath $root -Name "active-pending" -Statuses @("completed") -CompletedAt "2026-07-01T00:00:00+09:00"
    New-TestPhase -RootPath $root -Name "done-completed-at" -Statuses @("completed") -CompletedAt "2026-07-01T00:00:00+09:00"
    New-TestPhase -RootPath $root -Name "done-all-steps" -Statuses @("completed", "completed")
    New-TestPhase -RootPath $root -Name "blocked-phase" -Statuses @("blocked")
    New-Item -ItemType Directory -Force -Path (Join-Path $root ".dev\harness\phases\legacy-no-index") | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $root ".dev\harness\phases\_triage") | Out-Null

    Write-JsonFile (Join-Path $root ".dev\harness\phases\index.json") ([ordered]@{
        phases = @(
            [pscustomobject]@{ dir = "active-pending"; status = "pending" }
            [pscustomobject]@{ dir = "done-completed-at"; status = "completed" }
            [pscustomobject]@{ dir = "done-all-steps"; status = "completed" }
        )
    })

    Set-RepoRoot $root

    $plan = Get-PhaseCleanupPlan -Days 0
    $candidateNames = @($plan.Candidates | ForEach-Object { $_.Phase })
    Assert ($candidateNames -contains "done-completed-at") "completed_at phase is a cleanup candidate"
    Assert ($candidateNames -contains "done-all-steps") "all-completed phase is a cleanup candidate"
    Assert ($candidateNames -notcontains "active-pending") "top-index pending phase is not a candidate"
    Assert ($candidateNames -notcontains "blocked-phase") "blocked phase is not a candidate"
    Assert ($candidateNames -notcontains "legacy-no-index") "legacy phase without index is not a candidate"

    Invoke-Cleanup -Tokens @("-Days", "0", "-Apply")

    $archiveDirs = @(Get-ChildItem -Directory -LiteralPath (Join-Path $root ".dev\harness\phases\_archive"))
    Assert ($archiveDirs.Count -eq 1) "cleanup creates one timestamped archive batch"
    $archiveRoot = $archiveDirs[0].FullName
    Assert (Test-Path -LiteralPath (Join-Path $archiveRoot "done-completed-at\index.json")) "completed_at phase moved to archive"
    Assert (Test-Path -LiteralPath (Join-Path $archiveRoot "done-all-steps\index.json")) "all-completed phase moved to archive"
    Assert (Test-Path -LiteralPath (Join-Path $root ".dev\harness\phases\active-pending\index.json")) "active phase stays in phases"
    Assert (Test-Path -LiteralPath (Join-Path $root ".dev\harness\phases\blocked-phase\index.json")) "blocked phase stays in phases"

    $top = Get-Content -Raw -LiteralPath (Join-Path $root ".dev\harness\phases\index.json") -Encoding UTF8 | ConvertFrom-Json
    $topNames = @($top.phases | ForEach-Object { $_.dir })
    Assert ($topNames -contains "active-pending") "active phase remains in top index"
    Assert ($topNames -notcontains "done-completed-at") "archived completed phase removed from top index"
    Assert ($topNames -notcontains "done-all-steps") "archived all-completed phase removed from top index"

    Write-Host ""
    Write-Host "PASS: phase cleanup"
} finally {
    if (Test-Path -LiteralPath $tmp) {
        Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}
