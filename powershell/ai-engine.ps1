#!/usr/bin/env pwsh
# ai-engine.ps1 — AI 하네스 공용 엔진 (gg-harness 플러그인 **정본**).
#
# 각 레포의 `ai.ps1` 은 이 파일을 dot-source 하는 얇은 shim 이다.
# ⛔ 로직을 레포로 복사하지 마라 — 2026-08-08 에 Coupang_v2 와 bookmart 가 각각 1,000줄짜리
#    사본을 들고 있었고, **양쪽이 서로 다른 버그를 고쳐 서로 못 받고 있었다**
#    (bookmart: Write-Error 가 AI_EXIT_CODE 를 날리는 문제 / Coupang: run_record 결과 표시).
#    `wt.ps1` → `wt-engine.ps1` 과 같은 구조로 합쳤다.
#
# 진입점: Invoke-Ai -RepoRoot <path> -ToolPath <레포 ai.ps1 경로> -Command <cmd> -Rest <args>

$ErrorActionPreference = "Stop"

try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $script:OutputEncoding = [System.Text.UTF8Encoding]::new($false)
} catch {
    # Older hosts may not expose OutputEncoding setters. The commands still work.
}


function Set-RepoRoot {
    param([Parameter(Mandatory = $true)][string] $Path)

    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $top = (& git -C $resolved rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($top)) {
        throw "Not a git worktree: $Path"
    }

    $script:Root = [System.IO.Path]::GetFullPath($top.Trim())
    $script:PlansDir = Join-Path $script:Root ".dev\plans"
    $script:HarnessDir = Join-Path $script:Root ".dev\harness"
    $script:PhasesDir = Join-Path $script:HarnessDir "phases"
    $script:InboxDir = Join-Path $script:Root ".dev\inbox"
    $script:CloudDir = Join-Path $script:HarnessDir "cloud"
    $script:ReviewsDir = Join-Path $script:HarnessDir "reviews"
    $script:RunsDir = Join-Path $script:HarnessDir "runs"
    Set-Location -LiteralPath $script:Root
}


function Show-Help {
    @"
Usage:
  .\ai.ps1 status [-Repo path]
  .\ai.ps1 queue [-Repo path]
  .\ai.ps1 capture <name> [-Repo path] [-IncludeDiff] [-Copy]
  .\ai.ps1 run <name|plan-path> [-Repo path] [-Axis fe|be|arch] [-Phase name] [-Force] [-Provider codex|claude] [-NoBranch] [-Push] [-Unsafe] [-Model name] [-Timeout seconds]
  .\ai.ps1 review [name|plan-path|scope] [-Repo path] [-Axis fe|be|arch] [-Plan path] [-Base branch] [-IncludeDiff] [-Copy] [-NoRun] [-Model name]
  .\ai.ps1 loop <name|plan-path> [-Repo path] [-Axis fe|be|arch] [-Phase name] [-Force] [-Provider codex|claude] [-NoBranch] [-Push] [-Unsafe] [-Model name] [-Timeout seconds]
  .\ai.ps1 go <name|plan-path> [-Repo path] [-Axis fe|be|arch] [-Phase name] [-Force] [-Provider codex|claude] [-NoBranch] [-Push] [-Unsafe] [-Model name] [-Timeout seconds] [-NoRun] [-Here]
  .\ai.ps1 tasks [-Repo path]
  .\ai.ps1 tail [run-id] [-Repo path] [-Lines n]
  .\ai.ps1 stop [run-id|phase] [-Repo path] [-All]
  .\ai.ps1 prompt <name|plan-path> [-Repo path] [-Axis fe|be|arch] [-Copy] [-IncludeDiff]
  .\ai.ps1 cloud <name|plan-path> [-Repo path] [-Axis fe|be|arch] -Env <env-id> [-Branch branch] [-Attempts n] [-AllowDirty] [-IncludeDiff]

병렬 실행 (2026-08-08):
  런은 체크아웃마다 하나다. 이미 돌고 있는데 또 띄우면 go 가 **worktree 를 만들어 거기서 돌린다**
  (막지 않는다 — 병렬은 되는 게 맞다). 이 체크아웃에서 굳이 돌리려면 -Here.
  ★ 세션부터 가르는 게 낫다: .\wt.ps1 start <이름> 으로 claude 를 띄우면 터미널마다 체크아웃이 다르다.
  세울 땐 .\ai.ps1 stop — 러너만 죽이면 자식 execute.py 가 codex 를 계속 재생성한다.
  tasks·tail 은 **모든 worktree** 의 런을 함께 본다(남의 체크아웃 것은 wt=<폴더> 로 표시).
  stop 은 이 체크아웃만 — 죽이는 명령의 사정거리는 일부러 안 늘렸다.

Common flow:
  1. Claude plans only: create/update .dev/plans/*/*_plan.md
  2. Claude executes: /실행 <plan-name>  (runs .\ai.ps1 go <plan-name>)
  3. Claude checks progress: /상태      (runs .\ai.ps1 tasks)
  4. Manual fallback: .\ai.ps1 loop <name>

Notes:
  - Codex Cloud checks out a GitHub branch/commit. It cannot see local uncommitted work.
  - Use capture/prompt for handoff notes, or commit and push the branch before cloud execution.
  - Set CODEX_CLOUD_ENV to omit -Env.
"@
}

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]] $GitArgs)
    & git -C $Root @GitArgs
}

function Apply-RepoOption {
    param([hashtable] $Options)

    if ($Options["Repo"]) {
        Set-RepoRoot $Options["Repo"]
    }
}

function Get-RepoRelativePath {
    param([Parameter(Mandatory = $true)][string] $Path)
    $full = [System.IO.Path]::GetFullPath($Path)
    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
    if ($full.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $full.Substring($rootFull.Length).TrimStart('\').Replace('\', '/')
    }
    return $full
}

function Convert-ToSlug {
    param([Parameter(Mandatory = $true)][string] $Text)
    $slug = $Text -replace "_", "-"
    $slug = $slug -replace "[^0-9A-Za-z\p{IsHangulSyllables}-]+", "-"
    $slug = $slug -replace "-+", "-"
    $slug = $slug.Trim("-")
    if ([string]::IsNullOrWhiteSpace($slug)) {
        return "phase"
    }
    return $slug
}

function Get-PhaseNameFromPlan {
    param([Parameter(Mandatory = $true)][string] $PlanPath)
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($PlanPath)
    if ($stem.EndsWith("_plan", [System.StringComparison]::OrdinalIgnoreCase)) {
        $stem = $stem.Substring(0, $stem.Length - 5)
    }
    return Convert-ToSlug $stem
}

function Parse-Options {
    param([string[]] $Tokens)

    $options = @{}
    $positionals = New-Object System.Collections.Generic.List[string]

    for ($i = 0; $i -lt $Tokens.Count; $i++) {
        $token = $Tokens[$i]
        switch -Regex ($token) {
            '^-Plan$' {
                if ($i + 1 -ge $Tokens.Count) { throw "-Plan requires a value" }
                $i++
                $options["Plan"] = $Tokens[$i]
                continue
            }
            '^-Repo$|^-RepoRoot$' {
                if ($i + 1 -ge $Tokens.Count) { throw "$token requires a value" }
                $i++
                $options["Repo"] = $Tokens[$i]
                continue
            }
            '^-Axis$' {
                if ($i + 1 -ge $Tokens.Count) { throw "-Axis requires a value" }
                $i++
                $options["Axis"] = $Tokens[$i]
                continue
            }
            '^-Phase$' {
                if ($i + 1 -ge $Tokens.Count) { throw "-Phase requires a value" }
                $i++
                $options["Phase"] = $Tokens[$i]
                continue
            }
            '^-Provider$' {
                if ($i + 1 -ge $Tokens.Count) { throw "-Provider requires a value" }
                $i++
                $options["Provider"] = $Tokens[$i]
                continue
            }
            '^-Model$' {
                if ($i + 1 -ge $Tokens.Count) { throw "-Model requires a value" }
                $i++
                $options["Model"] = $Tokens[$i]
                continue
            }
            '^-Timeout$' {
                if ($i + 1 -ge $Tokens.Count) { throw "-Timeout requires a value" }
                $i++
                $options["Timeout"] = $Tokens[$i]
                continue
            }
            '^-Env$' {
                if ($i + 1 -ge $Tokens.Count) { throw "-Env requires a value" }
                $i++
                $options["Env"] = $Tokens[$i]
                continue
            }
            '^-Branch$' {
                if ($i + 1 -ge $Tokens.Count) { throw "-Branch requires a value" }
                $i++
                $options["Branch"] = $Tokens[$i]
                continue
            }
            '^-Attempts$' {
                if ($i + 1 -ge $Tokens.Count) { throw "-Attempts requires a value" }
                $i++
                $options["Attempts"] = $Tokens[$i]
                continue
            }
            '^-Base$' {
                if ($i + 1 -ge $Tokens.Count) { throw "-Base requires a value" }
                $i++
                $options["Base"] = $Tokens[$i]
                continue
            }
            '^-Lines$' {
                if ($i + 1 -ge $Tokens.Count) { throw "-Lines requires a value" }
                $i++
                $options["Lines"] = $Tokens[$i]
                continue
            }
            '^-IncludeDiff$' { $options["IncludeDiff"] = $true; continue }
            '^-Copy$' { $options["Copy"] = $true; continue }
            '^-NoRun$' { $options["NoRun"] = $true; continue }
            '^-Here$' { $options["Here"] = $true; continue }
            '^-Force$' { $options["Force"] = $true; continue }
            '^-NoBranch$' { $options["NoBranch"] = $true; continue }
            '^-Push$' { $options["Push"] = $true; continue }
            '^-Unsafe$' { $options["Unsafe"] = $true; continue }
            '^-AllowDirty$' { $options["AllowDirty"] = $true; continue }
            default {
                if ($token.StartsWith("-")) { throw "Unknown option: $token" }
                $positionals.Add($token) | Out-Null
            }
        }
    }

    [pscustomobject]@{
        Options = $options
        Positionals = $positionals
    }
}

function Get-PlanFiles {
    param([string] $Axis)

    $searchRoot = $PlansDir
    if ($Axis) {
        $searchRoot = Join-Path $PlansDir $Axis
    }
    if (-not (Test-Path $searchRoot)) {
        return @()
    }

    @(Get-ChildItem -Path $searchRoot -Recurse -File -Filter "*_plan.md" |
        Where-Object { $_.Name -ne "_template.md" } |
        Sort-Object LastWriteTime -Descending)
}

function Resolve-Plan {
    param(
        [string] $Query,
        [string] $Plan,
        [string] $Axis
    )

    if ($Plan) {
        $path = $Plan
        if (-not [System.IO.Path]::IsPathRooted($path)) {
            $path = Join-Path $Root $path
        }
        if (-not (Test-Path $path)) { throw "Plan not found: $Plan" }
        return (Resolve-Path $path).Path
    }

    if ([string]::IsNullOrWhiteSpace($Query)) {
        throw "Plan name or -Plan path is required"
    }

    $direct = $Query
    if (-not [System.IO.Path]::IsPathRooted($direct)) {
        $direct = Join-Path $Root $direct
    }
    if (Test-Path $direct) {
        return (Resolve-Path $direct).Path
    }

    $plans = Get-PlanFiles -Axis $Axis
    $exact = @($plans | Where-Object {
        $_.BaseName -eq $Query -or
        $_.BaseName -eq "${Query}_plan" -or
        (Get-PhaseNameFromPlan $_.FullName) -eq $Query
    })
    if ($exact.Count -eq 1) { return $exact[0].FullName }

    $matches = @($plans | Where-Object {
        $_.Name -like "*$Query*" -or
        (Get-RepoRelativePath $_.FullName) -like "*$Query*" -or
        (Get-PhaseNameFromPlan $_.FullName) -like "*$Query*"
    })

    if ($matches.Count -eq 1) { return $matches[0].FullName }
    if ($matches.Count -eq 0) { throw "No plan matched: $Query" }

    $sample = ($matches | Select-Object -First 10 | ForEach-Object { "  - " + (Get-RepoRelativePath $_.FullName) }) -join "`n"
    throw "Multiple plans matched '$Query'. Narrow with -Axis or -Plan:`n$sample"
}

function Get-GitStatusLines {
    $raw = @(Invoke-Git status --short --untracked-files=all)
    if ($LASTEXITCODE -ne 0) { throw "git status failed" }
    return @($raw | Where-Object { $_ -ne $null -and $_.Length -gt 0 })
}

function Get-CurrentBranch {
    $branch = Invoke-Git rev-parse --abbrev-ref HEAD
    if ($LASTEXITCODE -ne 0) { return "(unknown)" }
    return ($branch | Select-Object -First 1)
}

function Write-PhaseSummary {
    $indexPath = Join-Path $PhasesDir "index.json"
    if (-not (Test-Path $indexPath)) {
        Write-Host "Phases: none"
        return
    }

    try {
        $index = Get-Content -Raw $indexPath | ConvertFrom-Json
    } catch {
        Write-Host "Phases: index unreadable"
        return
    }

    $phases = @($index.phases)
    if ($phases.Count -eq 0) {
        Write-Host "Phases: none"
        return
    }

    Write-Host "Phases:"
    foreach ($phase in $phases | Select-Object -First 20) {
        Write-Host ("  - {0}: {1}" -f $phase.dir, $phase.status)
    }
}

function Invoke-Status {
    Write-Host ("Repo:   {0}" -f $Root)
    Write-Host ("Branch: {0}" -f (Get-CurrentBranch))
    $status = Get-GitStatusLines
    Write-Host ("Dirty:  {0} path(s)" -f $status.Count)
    if ($status.Count -gt 0) {
        $status | Select-Object -First 30 | ForEach-Object { Write-Host ("  {0}" -f $_) }
        if ($status.Count -gt 30) { Write-Host ("  ... {0} more" -f ($status.Count - 30)) }
    }
    Write-PhaseSummary
}

function Invoke-Queue {
    $plans = Get-PlanFiles
    Write-Host "Plans:"
    if ($plans.Count -eq 0) {
        Write-Host "  (none)"
    } else {
        foreach ($plan in $plans | Select-Object -First 40) {
            $rel = Get-RepoRelativePath $plan.FullName
            $statusLine = ""
            $match = Select-String -Path $plan.FullName -Pattern "^(상태|Status)\s*:" -List -ErrorAction SilentlyContinue
            if ($match) { $statusLine = " | " + $match.Line.Trim() }
            Write-Host ("  - {0}{1}" -f $rel, $statusLine)
        }
        if ($plans.Count -gt 40) { Write-Host ("  ... {0} more" -f ($plans.Count - 40)) }
    }
    Write-Host ""
    Write-PhaseSummary
}

function Get-PlanCandidateLines {
    $plans = Get-PlanFiles
    if ($plans.Count -eq 0) { return @("- (none)") }
    return @($plans | Select-Object -First 30 | ForEach-Object { "- " + (Get-RepoRelativePath $_.FullName) })
}

function Get-PhaseCandidateLines {
    $indexPath = Join-Path $PhasesDir "index.json"
    if (-not (Test-Path $indexPath)) { return @("- (none)") }
    try {
        $index = Get-Content -Raw $indexPath | ConvertFrom-Json
        $phases = @($index.phases)
        if ($phases.Count -eq 0) { return @("- (none)") }
        return @($phases | Select-Object -First 30 | ForEach-Object { "- $($_.dir): $($_.status)" })
    } catch {
        return @("- index unreadable")
    }
}

function New-Capture {
    param([string] $Name, [bool] $IncludeDiff, [bool] $Copy)

    if ([string]::IsNullOrWhiteSpace($Name)) { $Name = "terminal-handoff" }
    New-Item -ItemType Directory -Force -Path $InboxDir | Out-Null

    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $slug = Convert-ToSlug $Name
    $path = Join-Path $InboxDir "$stamp-$slug.md"
    $rel = Get-RepoRelativePath $path

    $branch = Get-CurrentBranch
    $status = Get-GitStatusLines
    $plans = Get-PlanCandidateLines
    $phases = Get-PhaseCandidateLines
    $diff = ""
    if ($IncludeDiff) {
        $trackedDiff = Invoke-Git diff -- .
        $diff = @"

## Tracked Diff

~~~diff
$($trackedDiff -join "`n")
~~~
"@
    }

    $body = @"
# Terminal Handoff: $Name

- captured_at: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz")
- repo: $Root
- branch: $branch
- note: This is an inbox capture, not the source of truth. Convert it into .dev/plans/*/*_plan.md before implementation when the scope is non-trivial.

## What I was trying to do

- TODO: Summarize the unfinished terminal task in 3-5 bullets.

## Current Git Status

~~~text
$($status -join "`n")
~~~

## Relevant Plans

$($plans -join "`n")

## Harness Phases

$($phases -join "`n")
$diff

## Next Handoff

- For Claude planning: turn this into a .dev/research note and .dev/plans/*/*_plan.md with a Codex handoff.
- For local Codex: run .\ai.ps1 run <plan-name>.
- For Codex Cloud: commit/push the branch or run .\ai.ps1 prompt <plan-name> -Copy.
"@

    Set-Content -Path $path -Value ($body.TrimEnd() + "`n") -Encoding UTF8
    if ($Copy) {
        Set-Clipboard -Value $path
    }
    Write-Host "Captured: $rel"
    if ($Copy) { Write-Host "Path copied to clipboard." }
}

function Ensure-Phase {
    param(
        [Parameter(Mandatory = $true)][string] $PlanPath,
        [string] $Phase,
        [bool] $Force
    )

    if ([string]::IsNullOrWhiteSpace($Phase)) {
        $Phase = Get-PhaseNameFromPlan $PlanPath
    } else {
        $Phase = Convert-ToSlug $Phase
    }

    $phaseDir = Join-Path $PhasesDir $Phase
    if ((Test-Path $phaseDir) -and -not $Force) {
        return $Phase
    }

    $args = @(".dev\harness\plan_to_phase.py", (Get-RepoRelativePath $PlanPath), "--phase", $Phase)
    if ($Force) { $args += "--force" }
    # Out-Host 필수: 캡처하지 않으면 plan_to_phase 의 stdout 이 이 함수의 리턴값에 섞여
    # $Phase 가 배열이 되고, 호출부의 execute.py 인자가 밀린다(첫 phase 생성 때만 터진다).
    & python @args | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "plan_to_phase failed" }
    return $Phase
}

function Invoke-Run {
    param([string[]] $Tokens)

    $parsed = Parse-Options $Tokens
    $opts = $parsed.Options
    Apply-RepoOption $opts
    $query = if ($parsed.Positionals.Count -gt 0) { $parsed.Positionals[0] } else { $null }
    $plan = Resolve-Plan -Query $query -Plan $opts["Plan"] -Axis $opts["Axis"]
    $phase = Ensure-Phase -PlanPath $plan -Phase $opts["Phase"] -Force ([bool]$opts["Force"])

    $provider = if ($opts["Provider"]) { $opts["Provider"] } else { "codex" }
    $execArgs = @(".dev\harness\execute.py", $phase, "--provider", $provider)
    if ($opts["Model"]) { $execArgs += @("--model", $opts["Model"]) }
    if ($opts["Timeout"]) { $execArgs += @("--timeout", $opts["Timeout"]) }
    if ($opts["NoBranch"]) { $execArgs += "--no-branch" }
    if ($opts["Push"]) { $execArgs += "--push" }
    if ($opts["Unsafe"]) { $execArgs += "--unsafe" }

    & python @execArgs
    exit $LASTEXITCODE
}

function Build-ReviewPrompt {
    param(
        [string] $Scope,
        [string] $PlanPath,
        [string] $Base,
        [bool] $IncludeDiff
    )

    New-Item -ItemType Directory -Force -Path $ReviewsDir | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $slugSource = if ($PlanPath) { Get-PhaseNameFromPlan $PlanPath } elseif ($Scope) { Convert-ToSlug $Scope } else { "worktree" }
    $promptPath = Join-Path $ReviewsDir "$stamp-$slugSource-review-prompt.md"
    $branch = Get-CurrentBranch
    $status = Get-GitStatusLines
    $scopeText = if ([string]::IsNullOrWhiteSpace($Scope)) { "current uncommitted worktree changes" } else { $Scope }
    $baseText = if ([string]::IsNullOrWhiteSpace($Base)) { "HEAD / current worktree" } else { $Base }

    $planSection = ""
    if ($PlanPath) {
        $planRel = Get-RepoRelativePath $PlanPath
        $planText = Get-Content -Raw $PlanPath
        $planSection = @"

## Source Plan

Path: $planRel

$planText
"@
    }

    $diffSection = ""
    if ($IncludeDiff) {
        $diffArgs = @("diff")
        if (-not [string]::IsNullOrWhiteSpace($Base)) { $diffArgs += $Base }
        $diffArgs += "--"
        $trackedDiff = Invoke-Git @diffArgs
        $diffSection = @"

## Tracked Diff Snapshot

~~~diff
$($trackedDiff -join "`n")
~~~
"@
    }

    $prompt = @"
# Codex Review Loop

You are the review agent for this repository. Do not implement, edit files, stage, commit, push, run migrations, or perform production writes.

## Review Scope

- repo: $Root
- branch: $branch
- base: $baseText
- scope: $scopeText

## Current Git Status

~~~text
$($status -join "`n")
~~~

## Required Review Loop

1. Read `CLAUDE.md`, `AGENTS.md`, and any relevant app-level `CLAUDE.md`.
2. Inspect the requested diff/scope with read-only commands.
3. If a plan exists, compare the diff against the plan's `Codex 인수인계`, acceptance criteria, and verification commands.
4. Report only consequential findings first: P0/P1 bugs, operational risk, missing tests, scope drift, or broken validation.
5. Separate findings into:
   - `Codex fix loop`: safe to hand back to implementation.
   - `Owner decision`: needs product/business judgment.
   - `Next plan`: out of current scope.
6. If the same validation failure appears already attempted twice, do not recommend another blind fix; ask for a narrower diagnosis.

## Output Format

Start with findings:

~~~text
- [P0|P1|P2] file:line - issue
  Impact:
  Fix:
  Loop bucket:
~~~

If there are no blocking issues, say `발견된 차단 이슈 없음`.
Then list verification gaps and the exact next command to run, such as:

~~~powershell
.\ai.ps1 run <plan-name> -Axis <axis>
.\ai.ps1 review <plan-name> -Axis <axis>
~~~
$planSection
$diffSection
"@

    Set-Content -Path $promptPath -Value ($prompt.TrimEnd() + "`n") -Encoding UTF8
    return $promptPath
}

function Invoke-Review {
    param([string[]] $Tokens)

    $parsed = Parse-Options $Tokens
    $opts = $parsed.Options
    Apply-RepoOption $opts
    $scope = ($parsed.Positionals -join " ").Trim()
    $plan = $null

    if ($opts["Plan"]) {
        $plan = Resolve-Plan -Query $null -Plan $opts["Plan"] -Axis $opts["Axis"]
    } elseif ($parsed.Positionals.Count -eq 1) {
        try {
            $plan = Resolve-Plan -Query $parsed.Positionals[0] -Plan $null -Axis $opts["Axis"]
            $scope = "Plan: $(Get-RepoRelativePath $plan)"
        } catch {
            # A single positional can also be a free-form review scope.
        }
    }

    $promptPath = Build-ReviewPrompt -Scope $scope -PlanPath $plan -Base $opts["Base"] -IncludeDiff ([bool]$opts["IncludeDiff"])
    $rel = Get-RepoRelativePath $promptPath
    if ($opts["Copy"]) {
        Set-Clipboard -Value (Get-Content -Raw $promptPath)
    }

    Write-Host "Review prompt: $rel"
    if ($opts["Copy"]) { Write-Host "Review prompt copied to clipboard." }
    if ($opts["NoRun"]) { return 0 }

    $prompt = Get-Content -Raw $promptPath
    $reviewArgs = @("exec", "--cd", $Root, "--dangerously-bypass-hook-trust", "--sandbox", "read-only")
    if ($opts["Model"]) { $reviewArgs += @("--model", $opts["Model"]) }
    $reviewArgs += "-"

    $prompt | & codex @reviewArgs | Out-Host
    return $LASTEXITCODE
}

function Invoke-Loop {
    param([string[]] $Tokens)

    $parsed = Parse-Options $Tokens
    $opts = $parsed.Options
    Apply-RepoOption $opts
    $query = if ($parsed.Positionals.Count -gt 0) { $parsed.Positionals[0] } else { $null }
    $plan = Resolve-Plan -Query $query -Plan $opts["Plan"] -Axis $opts["Axis"]
    $phase = Ensure-Phase -PlanPath $plan -Phase $opts["Phase"] -Force ([bool]$opts["Force"])

    $provider = if ($opts["Provider"]) { $opts["Provider"] } else { "codex" }
    $execArgs = @(".dev\harness\execute.py", $phase, "--provider", $provider)
    if ($opts["Model"]) { $execArgs += @("--model", $opts["Model"]) }
    if ($opts["Timeout"]) { $execArgs += @("--timeout", $opts["Timeout"]) }
    if ($opts["NoBranch"]) { $execArgs += "--no-branch" }
    if ($opts["Push"]) { $execArgs += "--push" }
    if ($opts["Unsafe"]) { $execArgs += "--unsafe" }

    & python @execArgs
    $runExit = $LASTEXITCODE
    if ($runExit -ne 0) {
        Write-Warning "Implementation loop failed; review skipped. Run '.\ai.ps1 review $(Get-RepoRelativePath $plan) -NoRun' if you need a review prompt."
        exit $runExit
    }

    Write-Host ""
    Write-Host "Implementation loop completed. Starting read-only Codex review."
    $reviewTokens = @("-Repo", $Root, "-Plan", $plan)
    if ($opts["Axis"]) { $reviewTokens += @("-Axis", $opts["Axis"]) }
    if ($opts["Model"]) { $reviewTokens += @("-Model", $opts["Model"]) }
    $reviewExit = Invoke-Review -Tokens $reviewTokens
    exit $reviewExit
}

function Quote-PowerShellLiteral {
    param([Parameter(Mandatory = $true)][string] $Value)
    return "'" + ($Value -replace "'", "''") + "'"
}

function Get-RunExitCode {
    param([Parameter(Mandatory = $true)][string] $LogPath)
    if (-not (Test-Path $LogPath)) { return $null }
    $marker = Get-Content -Path $LogPath -Tail 50 -ErrorAction SilentlyContinue |
        Where-Object { $_ -match "^AI_EXIT_CODE=" } |
        Select-Object -Last 1
    if (-not $marker) { return $null }
    return ($marker -replace "^AI_EXIT_CODE=", "").Trim()
}

function Get-RunRecords {
    if (-not (Test-Path $RunsDir)) { return @() }
    return @(Get-ChildItem -Path $RunsDir -File -Filter "*.json" |
        Sort-Object LastWriteTime -Descending |
        ForEach-Object {
            try {
                Get-Content -Raw $_.FullName | ConvertFrom-Json
            } catch {
                $null
            }
        } | Where-Object { $_ -ne $null })
}

# 모든 worktree 의 런 기록. **읽기 전용 조회(tasks·tail)에서만** 쓴다.
#   왜: 엔진이 런을 격리 worktree 로 옮기니까(Invoke-Go), 본체에서 `tasks` 를 쳐도 그 런이
#   안 보였다 — 실측(2026-08-08): 본체엔 낡은 런 6개만, `-Repo <worktree>` 를 줘야 [running] 이
#   보였고 `tail` 은 "No background runs found." 였다.
#
# ⛔ Get-RunRecords(=현재 체크아웃만) 를 이걸로 갈아치우지 마라. 나머지 셋은 일부러 뺐다:
#   - Invoke-Go: 알고 싶은 건 "**이** 체크아웃이 바쁘냐"다. 전체를 보면 옆 worktree 에 런이
#     하나만 살아 있어도 이 체크아웃을 바쁘다고 읽어 엉뚱하게 또 격리한다.
#   - Invoke-Stop: 죽이는 명령의 사정거리는 늘리지 않는다 — 전체를 보면 아무 폴더에서 친
#     `stop -All` 이 남의 런까지 죽인다.
function Get-AllRunRecords {
    param([int] $Limit = 0)

    # 경로를 짐작하지 않는다 — git 에게 묻는다(Invoke-Go 의 porcelain 파싱과 같은 방식).
    # worktree 가 없는 레포에선 본체 한 줄만 나온다.
    $roots = @{}
    $roots[$Root.ToLowerInvariant()] = $Root
    foreach ($line in @(& git -C $Root worktree list --porcelain 2>$null)) {
        if ($line -like "worktree *") {
            $p = $line.Substring(9).Trim()
            if ($p) {
                $full = [System.IO.Path]::GetFullPath($p)
                if (-not $roots.ContainsKey($full.ToLowerInvariant())) { $roots[$full.ToLowerInvariant()] = $full }
            }
        }
    }

    # 파일 목록을 먼저 정렬·자른 뒤 파싱한다 — worktree 40개 분량 json 을 다 파싱하고
    # 12개로 자르는 건 낭비다.
    $files = @()
    foreach ($r in $roots.Values) {
        $dir = Join-Path $r ".dev\harness\runs"
        if (-not (Test-Path $dir)) { continue }
        foreach ($f in @(Get-ChildItem -Path $dir -File -Filter "*.json" -ErrorAction SilentlyContinue)) {
            $files += [pscustomobject]@{ File = $f; RunRoot = $r }
        }
    }
    $files = @($files | Sort-Object { $_.File.LastWriteTime } -Descending)
    if ($Limit -gt 0) { $files = @($files | Select-Object -First $Limit) }

    return @($files | ForEach-Object {
        try {
            $rec = Get-Content -Raw $_.File.FullName | ConvertFrom-Json
            # 레코드의 log·runner 는 **자기 worktree** 기준 상대경로다. 어디서 왔는지 달아 두지
            # 않으면 남의 레코드를 `Join-Path $Root` 로 풀어 없는 파일을 가리킨다.
            $rec | Add-Member -NotePropertyName _root -NotePropertyValue $_.RunRoot -Force
            $rec
        } catch {
            $null
        }
    } | Where-Object { $_ -ne $null })
}

# 레코드가 온 체크아웃. 옛 레코드(_root 없음)는 현재 root 로 폴백한다.
function Get-RunRecordRoot {
    param([Parameter(Mandatory = $true)] $Record)
    if ($Record._root) { return $Record._root }
    return $Root
}

# 2026-08-08: pid 만 보고 "살아 있다"고 판정하면 **PID 재사용에 속는다.**
#   실측 — 12:44 에 죽은 런의 pid 47936 이 15:08 에 시작한 node_repl 로 재사용돼
#   `tasks` 가 [running] 을 찍었다. 그대로 죽였으면 남의 프로세스를 죽였다.
#   그래서 pid 뿐 아니라 **프로세스 시작시각**까지 대조한다(기록에 있을 때만).
function Test-RunAlive {
    param([Parameter(Mandatory = $true)] $Record)

    if (-not $Record.pid) { return $false }
    $proc = Get-Process -Id ([int]$Record.pid) -ErrorAction SilentlyContinue
    if (-not $proc) { return $false }

    # 옛 기록엔 pid_started_at 이 없다 — 그땐 **이름**으로 거른다. 러너는 항상 pwsh 라
    # 재사용된 pid 가 다른 프로그램이면 여기서 걸린다(실측: node_repl 이 [running] 으로 보였다).
    if (-not $Record.pid_started_at) { return ($proc.ProcessName -eq "pwsh") }

    try {
        $recorded = [datetime]::Parse($Record.pid_started_at).ToUniversalTime()
        $actual = $proc.StartTime.ToUniversalTime()
        # 기록은 Start-Process 직후라 실제 시작보다 수백 ms 늦을 수 있다.
        return ([math]::Abs(($actual - $recorded).TotalSeconds) -le 5)
    } catch {
        return $true   # StartTime 을 못 읽는 경우(권한 등)는 살아있는 쪽으로 본다
    }
}

# 프로세스 트리를 통째로 세운다.
#   왜: `Start-Process pwsh` 로 띄운 러너를 죽여도 **자식 `execute.py` 가 살아남아
#   codex 를 계속 재생성한다**(2026-08-08 실측: 15:13:38 죽였는데 15:17:24 에 새 codex).
#   Windows 는 프로세스 그룹이 없어 부모를 죽여도 자식이 고아로 남는다 → 직접 훑는다.
function Stop-ProcessTree {
    param([Parameter(Mandatory = $true)][int] $ProcessId, [int] $Depth = 0)

    if ($Depth -gt 6) { return @() }   # 순환 방어
    $killed = @()
    $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue)
    foreach ($c in $children) {
        $killed += Stop-ProcessTree -ProcessId ([int]$c.ProcessId) -Depth ($Depth + 1)
    }
    $self = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    if ($self) {
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
        $killed += [pscustomobject]@{ pid = $ProcessId; name = $self.Name }
    }
    return $killed
}

# 이 체크아웃에서 지금 돌고 있는 런.
function Get-LiveRunRecords {
    return @(Get-RunRecords | Where-Object { Test-RunAlive $_ })
}

function Invoke-Go {
    param([string[]] $Tokens)

    $parsed = Parse-Options $Tokens
    $opts = $parsed.Options
    Apply-RepoOption $opts
    $query = if ($parsed.Positionals.Count -gt 0) { $parsed.Positionals[0] } else { $null }
    $plan = Resolve-Plan -Query $query -Plan $opts["Plan"] -Axis $opts["Axis"]
    $phase = Ensure-Phase -PlanPath $plan -Phase $opts["Phase"] -Force ([bool]$opts["Force"])

    # ★ 격리가 기본이다 (2026-08-08). 이유가 둘이고, 둘 다 실측 사고다.
    #
    #   (1) **본체 체크아웃에서 돌면 안 된다.** 본체엔 늘 사람의 미커밋 작업이 얹혀 있다.
    #       실측: 본체에 다른 작업의 미커밋 리팩터(`core/services/wing_ops/` 미추적 + `winglib/*.py` 7개)가
    #       있는 채로 런이 돌아, `_commit_step` 이 **남의 파일까지 같이 커밋했다.**
    #       사람이 손으로 뽑아내야 했다.
    #   (2) **한 체크아웃에서 두 런이 겹치면 안 된다.** 서로의 브랜치를 밟는다.
    #       실측: 본체에서 `cdp-계정선택-공용화` 가 도는 중에 `패키지-계층-재설계` 를 띄웠더니
    #       뒤엣것이 트리를 자기 브랜치로 스위치했고, **앞엣것의 step 0 커밋이 남의 브랜치에 떨어졌다.**
    #
    #   막지 않고 옮긴다 — 병렬은 되는 게 맞다. worktree 를 만들어 거기서 돈다.
    #   빠져나갈 문: -Here (이 체크아웃에서 그냥 돌린다)
    $live = @(Get-LiveRunRecords)
    # 주 worktree 판별 — `git rev-parse --git-dir` 이 링크된 worktree 에선 `.git/worktrees/<이름>` 을 준다.
    $gitDir = (& git -C $Root rev-parse --git-dir 2>$null)
    $isPrimary = -not ($gitDir -and ($gitDir -replace "\\", "/") -match "/worktrees/")

    if ((-not $opts["Here"]) -and ($isPrimary -or $live.Count -gt 0)) {
        if ($live.Count -gt 0) {
            $busy = ($live | ForEach-Object { "{0} (phase={1}, pid={2})" -f $_.id, $_.phase, $_.pid }) -join "; "
            Write-Host "이 체크아웃은 이미 런이 돌고 있다: $busy"
        }
        if ($isPrimary) {
            Write-Host "여기는 본체 체크아웃이다 — 사람의 미커밋 작업이 커밋에 섞인다."
        }
        Write-Host "→ 격리 worktree 로 옮겨 실행한다. (굳이 여기서 돌리려면 -Here)"

        # ⚠️ worktree 스크립트 이름이 레포마다 다르다 — Coupang_v2 는 `wt.ps1`,
        #    bookmart 는 `_scripts/bmwt.ps1`. 둘 다 같은 공용 엔진(`wt-engine.ps1`)의 shim 이라
        #    `new <이름>` 인터페이스는 같다. 하나로 고정하면 반대편에서 격리가 죽는다.
        $wtScript = @("wt.ps1", "_scripts\bmwt.ps1", "bmwt.ps1") |
            ForEach-Object { Join-Path $Root $_ } |
            Where-Object { Test-Path $_ } |
            Select-Object -First 1
        if (-not $wtScript) {
            throw "worktree 격리 실패: worktree 스크립트를 못 찾았다 (wt.ps1 · _scripts\bmwt.ps1). -Here 로 강행하거나 직접 -Repo 를 줘라."
        }

        # 이름 충돌을 피하려고 phase 뒤에 시각을 붙인다(같은 phase 를 두 번 격리할 수 있다).
        $wtName = "{0}-{1}" -f $phase, (Get-Date -Format "HHmmss")
        & $wtScript new $wtName | Out-Host

        # ⚠️ 경로를 짐작하지 마라 — 레포마다 worktree 디렉터리 이름이 다르고($Root 가 이미
        #    worktree 면 부모가 그 디렉터리라 한 겹 더 낀다), 이 엔진은 여러 레포가 공용으로 쓴다.
        #    git 에게 브랜치로 물어보는 게 유일하게 정확하다.
        $wtRoot = $null
        $porcelain = @(& git -C $Root worktree list --porcelain 2>$null)
        for ($i = 0; $i -lt $porcelain.Count; $i++) {
            # ⚠️ 브랜치 이름을 `refs/heads/$wtName` 으로 **고정 비교하지 마라** — 레포마다
            #    접두사가 다르다(Coupang_v2 는 없음, bookmart 는 `BranchPrefix='wip/'`).
            #    실측(2026-08-08): worktree 는 정상 생성됐는데 `wip/AI하네스정리-…` 를 못 찾아
            #    「git 이 모른다」로 죽었다. 끝부분으로 맞춘다.
            if ($porcelain[$i] -like "branch refs/heads/*$wtName") {
                for ($j = $i; $j -ge 0; $j--) {
                    if ($porcelain[$j] -like "worktree *") {
                        $wtRoot = $porcelain[$j].Substring(9).Trim()
                        break
                    }
                }
                break
            }
        }
        if (-not $wtRoot -or -not (Test-Path $wtRoot)) {
            throw "worktree 생성 실패: 브랜치 '$wtName' 의 worktree 를 git 이 모른다. -Here 로 강행하거나 직접 -Repo 를 줘라."
        }
        $wtRoot = (Resolve-Path -LiteralPath $wtRoot).Path

        # ⚠️ worktree 는 origin/main 에서 뜬다 — 이 체크아웃의 **커밋 안 된** plan·phase 는 안 따라온다.
        #    그 둘이 이 런의 입력이라, 안 옮기면 옛 계획으로 돈다. 무엇을 실어 보냈는지 찍는다.
        $carried = @()
        $phaseSrc = Join-Path $HarnessDir "phases\$phase"
        $phaseDst = Join-Path $wtRoot ".dev\harness\phases\$phase"
        if (Test-Path $phaseSrc) {
            New-Item -ItemType Directory -Force -Path $phaseDst | Out-Null
            # ⚠️ `Copy-Item <src> <dst> -Recurse` 는 **dst 폴더가 이미 있으면 그 안으로** 넣는다
            #    → `phases/<phase>/<phase>/index.json` 이 생기고, 정작 하네스가 읽는 바깥
            #    `index.json` 은 **옛 판 그대로**다. 실측(2026-08-08): 차단을 풀어 보냈는데
            #    워크트리엔 안 실려 같은 자리에서 또 blocked 됐다 — 조용히 옛 계획으로 돈다.
            #    `<src>\*` 로 **내용물**을 넣어야 한다.
            # ⚠️ 그리고 dst 가 **없을 때**는 반대로 dst 가 **파일**이 된다 — 소스 글롭이 여러 개면
            #    `-Force` 가 매 항목마다 덮어 **마지막 파일 하나만** 남고, 하네스는 폴더를 못 찾아
            #    죽는다. 실측(2026-08-08, 오늘 세 번째): `회계보드-축-소급` 이 7,065바이트
            #    `step3.md` 사본이 됐고 런은 2초 만에 `not found` / `AI_EXIT_CODE=1`.
            #    부모(`Split-Path -Parent`)가 아니라 **dst 를** 만들어야 양쪽이 다 닫힌다.
            Copy-Item (Join-Path $phaseSrc "*") $phaseDst -Recurse -Force
            $carried += ".dev/harness/phases/$phase"
        }
        $planRel = Get-RepoRelativePath $plan
        $planDst = Join-Path $wtRoot ($planRel -replace "/", "\")
        if (Test-Path $plan) {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $planDst) | Out-Null
            Copy-Item $plan $planDst -Force
            $carried += $planRel
        }
        if ($carried.Count -gt 0) { Write-Host ("  실어 보냄(커밋 안 된 입력): {0}" -f ($carried -join ", ")) }

        # 원래 토큰을 그대로 넘기되 -Repo 를 새 worktree 로 덮고 -Here 로 재귀를 막는다.
        $fwd = @()
        for ($i = 0; $i -lt $Tokens.Count; $i++) {
            if ($Tokens[$i] -match '^-Repo$|^-RepoRoot$') { $i++; continue }
            $fwd += $Tokens[$i]
        }
        $fwd += @("-Repo", $wtRoot, "-Here")
        # ⚠️ worktree 는 `wt.ps1` 이 만든 **자기 브랜치**를 이미 물고 있다. 여기서 또
        #    `feat-<phase>` 를 checkout 하려 들면 git 이 거부한다 — 같은 브랜치는 두 worktree 에
        #    동시에 못 올라간다. 실측: 본체가 `feat-패키지-계층-재설계` 를 물고 있어
        #    격리 런이 26초 만에 죽었다("is already used by worktree at ...").
        #
        # ⚠️★ 더 나쁜 경우 — 그 브랜치가 **예전 회차 것으로 이미 있으면** git 이 거부하지 않고
        #    **갈아탄다.** 그러면 갓 만든 최신 worktree 가 옛 base 로 되돌아간다.
        #    실측(2026-08-08): `ai-harness-setup` 이 `feat-ai-harness-setup`(71커밋 낡음)으로
        #    끌려가 **오늘 걷어낸 `.claude/commands/` 12개를 되살리는 diff** 를 만들었다.
        #    런은 exit 0 로 「성공」했다 — 조용한 낭비다.
        if (-not $opts["NoBranch"]) { $fwd += "-NoBranch" }

        # ⚠️ Set-RepoRoot 가 Set-Location 을 한다 — 자기 재호출은 같은 프로세스라
        #    돌아온 뒤 **호출자의 CWD 가 새 worktree 에 남는다.** 그러면 이어지는 `.\ai.ps1` 이
        #    엉뚱한 체크아웃의 스크립트를 부른다(2026-08-08 실측: 뒤이은 -Here 가
        #    "Unknown option" 으로 죽었다 — 옛 사본을 부른 것이다). 반드시 되돌린다.
        Push-Location -LiteralPath $Root
        try {
            & $ToolScriptPath go @fwd
        } finally {
            Pop-Location
            Set-RepoRoot $Root
        }
        return
    }

    New-Item -ItemType Directory -Force -Path $RunsDir | Out-Null

    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $runId = "$stamp-$phase"
    $logPath = Join-Path $RunsDir "$runId.log"
    $runnerPath = Join-Path $RunsDir "$runId.ps1"
    $metaPath = Join-Path $RunsDir "$runId.json"

    $loopTokens = @("-Repo", $Root, "-Plan", $plan, "-Phase", $phase)
    if ($opts["Axis"]) { $loopTokens += @("-Axis", $opts["Axis"]) }
    if ($opts["Provider"]) { $loopTokens += @("-Provider", $opts["Provider"]) }
    if ($opts["Model"]) { $loopTokens += @("-Model", $opts["Model"]) }
    if ($opts["Timeout"]) { $loopTokens += @("-Timeout", $opts["Timeout"]) }
    if ($opts["NoBranch"]) { $loopTokens += "-NoBranch" }
    if ($opts["Push"]) { $loopTokens += "-Push" }
    if ($opts["Unsafe"]) { $loopTokens += "-Unsafe" }

    $scriptPath = $ToolScriptPath
    $recordScript = Join-Path $HarnessDir "run_record.py"
    $venvPython = Join-Path $Root ".venv\Scripts\python.exe"
    $quotedLoopTokens = ($loopTokens | ForEach-Object { Quote-PowerShellLiteral $_ }) -join " "
    $runner = @"
`$ErrorActionPreference = "Continue"
Set-Location -LiteralPath $(Quote-PowerShellLiteral $Root)
& $(Quote-PowerShellLiteral $scriptPath) loop $quotedLoopTokens *>&1 | Tee-Object -FilePath $(Quote-PowerShellLiteral $logPath)
`$code = if (`$null -ne `$LASTEXITCODE) { `$LASTEXITCODE } elseif (`$?) { 0 } else { 1 }
Add-Content -LiteralPath $(Quote-PowerShellLiteral $logPath) -Value ("AI_RUN_FINISHED_AT=" + (Get-Date -Format o))
Add-Content -LiteralPath $(Quote-PowerShellLiteral $logPath) -Value ("AI_EXIT_CODE=" + `$code)
# 회차 기록에 결과를 적는다 — 이게 없으면 `.\ai.ps1 tasks` 가 "몇 연속 같은 사유로 실패"를 못 센다.
`$py = $(Quote-PowerShellLiteral $venvPython)
if (-not (Test-Path `$py)) { `$py = "python" }
try { & `$py $(Quote-PowerShellLiteral $recordScript) $(Quote-PowerShellLiteral $metaPath) `$code $(Quote-PowerShellLiteral $logPath) } catch { }
exit `$code
"@
    Set-Content -Path $runnerPath -Value $runner -Encoding UTF8

    if ($opts["NoRun"]) {
        Write-Host "Prepared Codex background loop."
        Write-Host ("Run:    {0}" -f $runId)
        Write-Host ("Phase:  {0}" -f $phase)
        Write-Host ("Runner: {0}" -f (Get-RepoRelativePath $runnerPath))
        Write-Host ("Log:    {0}" -f (Get-RepoRelativePath $logPath))
        return
    }

    $proc = Start-Process -FilePath "pwsh" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $runnerPath) `
        -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -PassThru

    # pid_started_at = **프로세스의** 시작시각(기록 시각이 아니다). PID 재사용 판별의 유일한 근거다.
    $pidStartedAt = try { $proc.StartTime.ToString("o") } catch { $null }

    $record = [pscustomobject]@{
        id = $runId
        pid = $proc.Id
        pid_started_at = $pidStartedAt
        repo = $Root
        started_at = (Get-Date -Format o)
        phase = $phase
        plan = (Get-RepoRelativePath $plan)
        log = (Get-RepoRelativePath $logPath)
        runner = (Get-RepoRelativePath $runnerPath)
        command = ".\ai.ps1 loop -Repo `"$Root`" -Plan `"$plan`" -Phase $phase"
    }
    $record | ConvertTo-Json -Depth 4 | Set-Content -Path $metaPath -Encoding UTF8

    Write-Host "Started Codex background loop."
    Write-Host ("Run:   {0}" -f $runId)
    Write-Host ("PID:   {0}" -f $proc.Id)
    Write-Host ("Phase: {0}" -f $phase)
    Write-Host ("Log:   {0}" -f (Get-RepoRelativePath $logPath))
    Write-Host ""
    Write-Host "Check later:"
    Write-Host ("  .\ai.ps1 tasks")
    Write-Host ("  .\ai.ps1 tail {0}" -f $runId)
}

function Invoke-Tasks {
    # 격리 worktree 로 옮겨 도는 런까지 본다 — 아니면 본체에서 `tasks` 를 쳐도 안 보인다.
    $records = Get-AllRunRecords -Limit 12
    Write-Host "Runs:"
    if ($records.Count -eq 0) {
        Write-Host "  (none)"
        return
    }

    foreach ($record in $records) {
        # pid 생존만 보면 PID 재사용에 속는다 — Test-RunAlive 가 시작시각까지 대조한다.
        $running = Test-RunAlive $record

        $recordRoot = Get-RunRecordRoot $record
        $logPath = Join-Path $recordRoot ($record.log -replace "/", "\")
        $exitCode = Get-RunExitCode -LogPath $logPath
        $state = if ($running) {
            "running"
        } elseif ($record.result) {
            # run_record.py 가 적은 결과가 있으면 그게 정본이다 (로그 마커는 옛 회차용 폴백).
            "{0}:{1}" -f $record.result, $record.exit_code
        } elseif ($null -eq $exitCode) {
            "exited?"
        } elseif ($exitCode -eq "0") {
            "completed"
        } else {
            "failed:$exitCode"
        }

        # 남의 체크아웃 런은 어디 것인지 보여야 한다 — 안 그러면 `tail`·`stop` 을 엉뚱한 폴더에서 친다.
        $where = if ([string]::Equals($recordRoot, $Root, [System.StringComparison]::OrdinalIgnoreCase)) {
            ""
        } else {
            " wt={0}" -f (Split-Path -Leaf $recordRoot)
        }
        Write-Host ("  - {0} [{1}] pid={2} phase={3}{4}" -f $record.id, $state, $record.pid, $record.phase, $where)
        if ($record.reason) { Write-Host ("    reason: {0}" -f $record.reason) }
        Write-Host ("    log: {0}" -f $record.log)
    }
}

function Invoke-Stop {
    param([string[]] $Tokens)

    $parsed = Parse-Options $Tokens
    $opts = $parsed.Options
    Apply-RepoOption $opts
    $query = if ($parsed.Positionals.Count -gt 0) { $parsed.Positionals[0] } else { $null }

    $live = @(Get-LiveRunRecords)
    if ($live.Count -eq 0) { Write-Host "돌고 있는 런이 없다."; return }

    $targets = if ([string]::IsNullOrWhiteSpace($query)) {
        if ($live.Count -gt 1) {
            Write-Host "런이 여러 개다 — 어느 것을 세울지 지정해라 (id 또는 phase 일부):"
            foreach ($r in $live) { Write-Host ("  - {0} (phase={1}, pid={2})" -f $r.id, $r.phase, $r.pid) }
            Write-Host "  전부 세우려면: .\ai.ps1 stop -All"
            if (-not $opts["All"]) { return }
        }
        $live
    } else {
        @($live | Where-Object { $_.id -like "*$query*" -or $_.phase -like "*$query*" })
    }

    if ($targets.Count -eq 0) { Write-Host "일치하는 런이 없다: $query"; return }

    foreach ($r in $targets) {
        Write-Host ("세운다: {0} (phase={1}, pid={2})" -f $r.id, $r.phase, $r.pid)
        # ⚠️ 러너 pwsh 만 죽이면 자식 execute.py 가 살아남아 codex 를 계속 재생성한다.
        #    자식부터 훑어 통째로 세운다.
        $killed = Stop-ProcessTree -ProcessId ([int]$r.pid)
        foreach ($k in $killed) { Write-Host ("  ✓ {0} ({1})" -f $k.pid, $k.name) }
        if ($killed.Count -eq 0) { Write-Host "  (이미 죽어 있었다)" }
    }

    Start-Sleep -Milliseconds 700
    $still = @(Get-LiveRunRecords | Where-Object { $targets.id -contains $_.id })
    if ($still.Count -gt 0) {
        Write-Warning ("아직 살아 있다: {0} — 다시 실행하거나 수동 확인해라." -f (($still | ForEach-Object { $_.id }) -join ", "))
    } else {
        Write-Host "전부 정지 확인됨."
    }
}

function Invoke-Tail {
    param([string[]] $Tokens)

    $parsed = Parse-Options $Tokens
    $opts = $parsed.Options
    Apply-RepoOption $opts
    $query = if ($parsed.Positionals.Count -gt 0) { $parsed.Positionals[0] } else { $null }
    $lines = if ($opts["Lines"]) { [int]$opts["Lines"] } else { 80 }
    # tasks 와 같은 시야여야 한다 — 목록에 보이는 런을 tail 이 못 찾으면 안 된다.
    # (query 로 걸러야 하니 여기선 자르지 않는다.)
    $records = Get-AllRunRecords
    if ($records.Count -eq 0) { throw "No background runs found." }

    $record = $null
    if ([string]::IsNullOrWhiteSpace($query)) {
        $record = $records | Select-Object -First 1
    } else {
        $matches = @($records | Where-Object {
            $_.id -like "*$query*" -or
            $_.phase -like "*$query*" -or
            $_.plan -like "*$query*"
        })
        if ($matches.Count -eq 0) { throw "No run matched: $query" }
        if ($matches.Count -gt 1) {
            $sample = ($matches | Select-Object -First 10 | ForEach-Object { "  - $($_.id) [$($_.phase)]" }) -join "`n"
            throw "Multiple runs matched '$query':`n$sample"
        }
        $record = $matches[0]
    }

    $logPath = Join-Path (Get-RunRecordRoot $record) ($record.log -replace "/", "\")
    if (-not (Test-Path $logPath)) { throw "Log not found: $logPath" }
    Write-Host ("Log: {0}" -f $logPath)
    Get-Content -Path $logPath -Tail $lines
}

function Build-CloudPrompt {
    param(
        [Parameter(Mandatory = $true)][string] $PlanPath,
        [bool] $IncludeDiff
    )

    New-Item -ItemType Directory -Force -Path $CloudDir | Out-Null
    $phase = Get-PhaseNameFromPlan $PlanPath
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $promptPath = Join-Path $CloudDir "$stamp-$phase-prompt.md"
    $planRel = Get-RepoRelativePath $PlanPath
    $branch = Get-CurrentBranch
    $status = Get-GitStatusLines
    $planText = Get-Content -Raw $PlanPath

    $diffSection = ""
    if ($IncludeDiff) {
        $trackedDiff = Invoke-Git diff -- .
        $diffSection = @"

## Local Tracked Diff

Codex Cloud cannot read local uncommitted files directly. This diff is pasted for context only; prefer commit/push for executable context.

~~~diff
$($trackedDiff -join "`n")
~~~
"@
    }

    $prompt = @"
# Codex Cloud Task

Repository root in cloud: use the connected GitHub repository for this project.
Local source plan: $planRel
Local branch when prompt was created: $branch

## Required Operating Rules

- Read AGENTS.md and CLAUDE.md first.
- Implement only the scope in the plan's Codex handoff.
- Reuse existing code before creating new modules.
- Do not perform production writes, destructive cleanup, merges, force push, or broad git add.
- Run the verification commands from the plan and report any skipped checks.
- Leave a focused diff for review; do not commit unless the cloud environment explicitly requires it.

## Local Git Status At Prompt Time

~~~text
$($status -join "`n")
~~~

## Plan

$planText
$diffSection
"@

    Set-Content -Path $promptPath -Value ($prompt.TrimEnd() + "`n") -Encoding UTF8
    return $promptPath
}

function Invoke-Prompt {
    param([string[]] $Tokens)

    $parsed = Parse-Options $Tokens
    $opts = $parsed.Options
    Apply-RepoOption $opts
    $query = if ($parsed.Positionals.Count -gt 0) { $parsed.Positionals[0] } else { $null }
    $plan = Resolve-Plan -Query $query -Plan $opts["Plan"] -Axis $opts["Axis"]
    $promptPath = Build-CloudPrompt -PlanPath $plan -IncludeDiff ([bool]$opts["IncludeDiff"])
    $rel = Get-RepoRelativePath $promptPath
    if ($opts["Copy"]) {
        Set-Clipboard -Value (Get-Content -Raw $promptPath)
    }
    Write-Host "Prompt: $rel"
    if ($opts["Copy"]) { Write-Host "Prompt copied to clipboard." }
}

function Invoke-Cloud {
    param([string[]] $Tokens)

    $parsed = Parse-Options $Tokens
    $opts = $parsed.Options
    Apply-RepoOption $opts
    $query = if ($parsed.Positionals.Count -gt 0) { $parsed.Positionals[0] } else { $null }
    $envId = if ($opts["Env"]) { $opts["Env"] } else { $env:CODEX_CLOUD_ENV }
    if ([string]::IsNullOrWhiteSpace($envId)) {
        throw "Cloud environment id is required. Use -Env <env-id> or set CODEX_CLOUD_ENV."
    }

    $dirty = Get-GitStatusLines
    if ($dirty.Count -gt 0 -and -not $opts["AllowDirty"] -and -not $opts["IncludeDiff"]) {
        throw "Working tree is dirty. Codex Cloud cannot see uncommitted local work. Commit/push first, or use -IncludeDiff for context, or -AllowDirty if the dirt is unrelated."
    }

    $plan = Resolve-Plan -Query $query -Plan $opts["Plan"] -Axis $opts["Axis"]
    $promptPath = Build-CloudPrompt -PlanPath $plan -IncludeDiff ([bool]$opts["IncludeDiff"])
    $prompt = Get-Content -Raw $promptPath
    if ($prompt.Length -gt 28000) {
        throw "Cloud prompt is too long for a command argument ($($prompt.Length) chars). Saved to $(Get-RepoRelativePath $promptPath). Shorten the plan or submit from the UI."
    }

    $attempts = if ($opts["Attempts"]) { [int]$opts["Attempts"] } else { 1 }
    $cloudArgs = @("cloud", "exec", "--env", $envId, "--attempts", "$attempts")
    if ($opts["Branch"]) {
        $cloudArgs += @("--branch", $opts["Branch"])
    }
    $cloudArgs += $prompt

    Write-Host ("Submitting Codex Cloud task from prompt: {0}" -f (Get-RepoRelativePath $promptPath))
    & codex @cloudArgs
    exit $LASTEXITCODE
}

function Invoke-Ai {
    param(
        [Parameter(Mandatory = $true)][string] $RepoRoot,
        [Parameter(Mandatory = $true)][string] $ToolPath,
        [string] $Command = "help",
        [string[]] $Rest
    )

    # shim 이 자기 경로를 준다 — 엔진 경로가 아니라 **레포의 ai.ps1** 이어야
    # Invoke-Go 의 자기 재호출(`& $ToolScriptPath go ...`)이 맞는 파일을 부른다.
    $script:ToolScriptPath = $ToolPath
    Set-RepoRoot $RepoRoot

    try {
        switch ($Command.ToLowerInvariant()) {
            "help" { Show-Help }
            "-h" { Show-Help }
            "--help" { Show-Help }
            "status" {
                $parsed = Parse-Options $Rest
                Apply-RepoOption $parsed.Options
                Invoke-Status
            }
            "queue" {
                $parsed = Parse-Options $Rest
                Apply-RepoOption $parsed.Options
                Invoke-Queue
            }
            "capture" {
                $parsed = Parse-Options $Rest
                Apply-RepoOption $parsed.Options
                $name = if ($parsed.Positionals.Count -gt 0) { $parsed.Positionals[0] } else { "terminal-handoff" }
                New-Capture -Name $name -IncludeDiff ([bool]$parsed.Options["IncludeDiff"]) -Copy ([bool]$parsed.Options["Copy"])
            }
            "run" { Invoke-Run -Tokens $Rest }
            "review" { exit (Invoke-Review -Tokens $Rest) }
            "loop" { Invoke-Loop -Tokens $Rest }
            "go" { Invoke-Go -Tokens $Rest }
            "start" { Invoke-Go -Tokens $Rest }
            "tasks" {
                $parsed = Parse-Options $Rest
                Apply-RepoOption $parsed.Options
                Invoke-Tasks
            }
            "tail" { Invoke-Tail -Tokens $Rest }
            "stop" { Invoke-Stop -Tokens $Rest }
            "kill" { Invoke-Stop -Tokens $Rest }
            "prompt" { Invoke-Prompt -Tokens $Rest }
            "cloud" { Invoke-Cloud -Tokens $Rest }
            default {
                throw "Unknown command: $Command"
            }
        }
    } catch {
        Write-Error $_.Exception.Message
        exit 1
    }
}
