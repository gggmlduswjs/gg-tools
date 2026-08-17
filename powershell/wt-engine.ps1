<#
wt-engine.ps1 — worktree 세션 격리 엔진 (프로젝트 공용)

왜 공용인가: 예전엔 bookmart(`_scripts/bmwt.ps1` 437줄)와 Coupang(`wt.ps1` 82줄)이
같은 일을 **두 벌**로 구현하고 있었다. 그래서 한쪽에서 배운 걸 다른 쪽이 못 받았다 —
2026-07-25 에 bookmart 가 `.venv` 정션 사고를 고쳤는데 Coupang 은 못 받아 07-28 에
같은 사고를 당했고(본체 `.venv` Lib/ 전소), squash 머지 오판(아래 Get-BranchLanded)은
반대로 bookmart 만 알고 있었다. 구현이 한 벌이면 고칠 때 둘 다 고쳐진다.

프로젝트별로 다른 것은 $cfg 4~6개뿐이고 나머지는 전부 공용이다.

쓰는 법 — 각 레포의 얇은 shim 이 이 파일을 dot-source 하고 Invoke-Wt 를 부른다:

    . "$HOME\claude\powershell\wt-engine.ps1"
    Invoke-Wt -Config @{
      Label='Coupang'; WtDir='Coupang_v2-wt'; BranchPrefix=''
      Provision=@('.env'); SessionsDir=$null; SweepRefs=@(); CleanHint='.\wt.ps1 rm <이름>'
    } -Command $Command -Rest $Rest

명령: start · new · provision · land · list · clean(=rm) · prune
#>

# ── git 헬퍼 ─────────────────────────────────────────────────────────────────
# PS5.1은 native exe의 stderr(진행 메시지 등)를 ErrorRecord로 감싸 $ErrorActionPreference=Stop
# 하에서 종료시킨다. git은 정상 진행도 stderr에 찍으므로, 2>&1로 캡처해 문자열로만 표시하고
# 성공/실패는 $LASTEXITCODE로만 판정한다.
function Invoke-GitShow {
  param([Parameter(ValueFromRemainingArguments = $true)]$GitArgs)
  $prev = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try { & git @GitArgs 2>&1 | ForEach-Object { Write-Host ([string]$_) } }
  finally { $ErrorActionPreference = $prev }
  return $LASTEXITCODE
}
function Invoke-Git {  # 실패 시 throw
  param([Parameter(ValueFromRemainingArguments = $true)]$GitArgs)
  if ((Invoke-GitShow @GitArgs) -ne 0) { throw "git $($GitArgs -join ' ') 실패" }
}
# 값 조회용(rev-parse 등): stderr 억제, 첫 줄만 반환.
function Get-GitValue {
  param([Parameter(ValueFromRemainingArguments = $true)]$GitArgs)
  return ((& git @GitArgs 2>$null) | Select-Object -First 1)
}

function Get-GitSafePath([string]$path) {
  return ([System.IO.Path]::GetFullPath($path)).Replace('\', '/')
}

function Get-GitLinesInPath {
  param([string]$Path, [Parameter(ValueFromRemainingArguments = $true)]$GitArgs)
  $safe = Get-GitSafePath $Path
  $prev = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    $lines = @(& git -c "safe.directory=$safe" --no-optional-locks -C $Path @GitArgs 2>$null)
    $code = $LASTEXITCODE
  }
  finally {
    $ErrorActionPreference = $prev
  }
  if ($code -ne 0) { throw "git -C $Path $($GitArgs -join ' ') 실패" }
  return $lines
}

function Get-GitValueInPath {
  param([string]$Path, [Parameter(ValueFromRemainingArguments = $true)]$GitArgs)
  return (Get-GitLinesInPath $Path @GitArgs | Select-Object -First 1)
}

function Test-CodexSandboxGitMutationBlocked {
  return [bool](
    $env:CODEX_THREAD_ID -and
    (($env:CODEX_PERMISSION_PROFILE -and $env:CODEX_PERMISSION_PROFILE -ne ':full') -or
     $env:CODEX_SANDBOX_NETWORK_DISABLED)
  )
}

# list/prune 은 조회 명령이다. Codex Windows sandbox 에서는 .git 이 읽기 전용이라
# FETCH_HEAD 를 쓰는 `git fetch` 가 막힐 수 있다. 그때 조회 자체가 죽으면 사람이
# 정리 대상을 볼 방법이 없어지므로, 기존 origin/<main> ref 로 계속 진행한다.
# 단, 실제 삭제(--apply)는 최신 ref 없이 진행하지 않는다(Invoke-Prune 쪽에서 차단).
function Update-OriginMainBestEffort {
  $script:OriginMainUpdateSkipped = $false
  if (Test-CodexSandboxGitMutationBlocked) {
    $script:OriginMainUpdateSkipped = $true
    Write-Host "Codex sandbox 조회 모드: git fetch 생략 — 기존 로컬 origin/$($script:MainBr) 기준." -ForegroundColor DarkYellow
    return $false
  }

  $prev = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  $out = @()
  try {
    $out = @(& git fetch origin $script:MainBr --quiet 2>&1)
    $ok = ($LASTEXITCODE -eq 0)
  }
  catch {
    $out = @($_)
    $ok = $false
  }
  finally {
    $ErrorActionPreference = $prev
  }
  if (-not $ok) {
    $msg = ($out | ForEach-Object { [string]$_ } | Where-Object { $_ } | Select-Object -First 1)
    if (-not $msg) { $msg = "git fetch origin $($script:MainBr) 실패" }
    Write-Warning "origin/$($script:MainBr) 갱신 실패 — 기존 로컬 ref 기준으로 조회만 계속: $msg"
  }
  return $ok
}

# main checkout 루트 = 공유 .git(git-common-dir)의 부모.
# worktree에서 실행해도 항상 main을 가리킨다($PSScriptRoot는 worktree-로컬이라 못 씀).
function Get-MainRoot {
  $common = Get-GitValue rev-parse --git-common-dir
  if (-not $common) { throw "git 레포가 아님" }
  return (Split-Path (Resolve-Path $common).Path -Parent)
}

# 레포 밖 형제 폴더 (레포 안에 두면 nested .git로 git status 오탐)
function Get-WorktreePath([string]$name, [string]$main) {
  return (Join-Path (Join-Path (Split-Path $main -Parent) $script:WtDir) $name)
}

function Get-BranchName([string]$name) { return "$($script:BranchPrefix)$name" }

# 조회는 조립하지 말고 등록된 것에서 찾는다 — worktree 가 두 곳에 생기기 때문이다:
#   · 이 엔진의 new/start  → ../<WtDir>/<name>
#   · Claude Code 의 EnterWorktree → <repo>/.claude/worktrees/<name>
# 조립 경로만 보던 clean 은 후자를 "없음"으로 거부했다(2026-08-04, 22/28 이 후자였다).
# 생성(new)은 아직 없는 경로를 만들어야 하니 Get-WorktreePath 를 그대로 쓴다.
function Resolve-WorktreePath([string]$name, [string]$main) {
  $hit = @(Get-WorktreeEntries | Where-Object { (Split-Path $_.path -Leaf) -eq $name })
  if ($hit.Count -eq 1) { return $hit[0].path }
  if ($hit.Count -gt 1) { throw "이름 중복 — 경로로 지정하라:`n  " + (($hit | ForEach-Object { $_.path }) -join "`n  ") }
  return (Get-WorktreePath $name $main)
}

# ★.venv 는 worktree 에 만들지 않는다 (bookmart 2026-07-25 · Coupang 2026-07-28).
# 정션은 본체 .venv 로 가는 **문**이라, worktree 폴더를 재귀 삭제하면(git worktree remove ·
# 탐색기 · Remove-Item 무엇이든) 삭제가 문을 따라 들어가 본체 .venv 를 파괴한다. 실사고 3회.
# 대신 러너·훅이 `git rev-parse --git-common-dir` 로 본체를 직접 찾는다 → 문이 필요 없다.
# 남은 레거시 정션은 clean/prune 이 `cmd /c rmdir`(reparse 만 제거·target 보존)로 치운다.
function Add-Provision([string]$wt, [string]$main) {
  $venvSrc = Join-Path $main '.venv'
  if (-not (Test-Path $venvSrc)) { Write-Warning ".venv 없음: $venvSrc — 본체에 venv 가 있어야 테스트/스크립트가 돈다" }
  foreach ($f in $script:Provision) {
    $src = Join-Path $main $f
    $dst = Join-Path $wt   $f
    if (-not (Test-Path $src)) { Write-Warning "$f 없음: $src"; continue }
    if (Test-Path $dst) { Write-Host "  $f 이미 있음 — 건너뜀"; continue }
    # ponytail: 복사. symlink 는 Windows 에서 admin/개발자모드 필요, .env 는 1KB 라 복사가 최소.
    Copy-Item $src $dst
    Write-Host "  $f → 복사"
  }
}

# worktree 폴더에 남은 reparse point(정션) 를 링크만 끊는다. **재귀 삭제 전에 반드시.**
function Remove-LegacyLinks([string]$wt) {
  foreach ($d in (Get-ChildItem $wt -Force -Directory -ErrorAction SilentlyContinue)) {
    if ($d.Attributes -band [IO.FileAttributes]::ReparsePoint) {
      cmd /c rmdir "$($d.FullName)" 2>$null | Out-Null
      Write-Host "  레거시 정션 끊음: $($d.Name)"
    }
  }
}

# ── new / start ──────────────────────────────────────────────────────────────
function New-Worktree([string]$name, [string]$main, [string]$wt) {
  New-Item -ItemType Directory -Force (Split-Path $wt -Parent) | Out-Null
  # ★base 를 반드시 origin/<main> 으로. 옛 코드는 base 없이 만들어 stale 한 로컬 HEAD 를 물려받았고
  #   (로컬 main 은 07-25 실측 27커밋 뒤처짐) 이미 머지된 걸 또 만드는 쌍둥이 커밋의 뿌리가 됐다.
  Invoke-Git fetch origin $script:MainBr
  Invoke-Git worktree add $wt -b (Get-BranchName $name) "origin/$($script:MainBr)"
  Write-Host "worktree 생성: $wt  (브랜치 $(Get-BranchName $name) · base origin/$($script:MainBr))"
}

function Invoke-New([string]$name) {
  if (-not $name) { throw "이름 필요: new <name>" }
  $main = Get-MainRoot
  $wt   = Get-WorktreePath $name $main
  if (Test-Path $wt) { throw "이미 있음: $wt" }
  New-Worktree $name $main $wt
  Add-Provision $wt $main
  Write-Host ""
  Write-Host "다음 세션은 여기서 시작:" -ForegroundColor Green
  Write-Host "  cd `"$wt`"; claude"
}

function Invoke-Start([string]$name, $extra) {
  # new + provision + '그 worktree에서 claude 실행'까지 한 번에.
  # 격리의 근본 해법: 세션을 처음부터 worktree 안에서 연다(켜진 뒤엔 못 옮김).
  if (-not $name) { throw "이름 필요: start <name>" }
  $main = Get-MainRoot
  $wt   = Get-WorktreePath $name $main
  if (-not (Test-Path $wt)) { New-Worktree $name $main $wt } else { Write-Host "worktree 재사용: $wt" }
  Add-Provision $wt $main
  Set-Location $wt
  if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Warning "claude CLI를 PATH에서 못 찾음 — 수동으로: cd `"$wt`"; claude"; return
  }
  Write-Host "claude 시작 (격리됨): $wt" -ForegroundColor Green
  & claude @extra
}

function Invoke-Provision([string]$path) {
  $target = if ($path) { (Resolve-Path $path).Path } else { (Get-Location).Path }
  $main   = Get-MainRoot
  if ($target -eq $main) { throw "여긴 main checkout — provision 대상은 worktree" }
  Write-Host "provision: $target"
  Add-Provision $target $main
}

function Invoke-Land {
  # worktree 안에서 실행 가정. rebase 만 하고 push(=배포)는 사람이 의도적으로.
  if ((Get-GitValue rev-parse --git-dir) -eq (Get-GitValue rev-parse --git-common-dir)) {
    throw "여긴 main checkout — land 는 worktree 안에서"
  }
  $branch = Get-GitValue rev-parse --abbrev-ref HEAD
  Invoke-Git fetch origin $script:MainBr
  if ((Invoke-GitShow rebase "origin/$($script:MainBr)") -ne 0) {
    throw "rebase 충돌 — 해결 후 'git rebase --continue', 그다음 다시 land"
  }
  Write-Host ""
  Write-Host "rebase 완료 ($branch). 배포하려면 아래를 직접 실행:" -ForegroundColor Green
  Write-Host "  git push origin HEAD:$($script:MainBr)"
  Write-Host "(push = GH Actions 배포. 안전을 위해 자동 실행하지 않음.)"
}

# ── 판정 ─────────────────────────────────────────────────────────────────────
$script:StaleMin = 30   # 훅의 STALE_SEC 과 같은 경계값(분). 갈리면 판정이 어긋난다.
$script:QuietH   = 12   # 조용함 게이트

# cwd(정규화) → 마지막 하트비트. 훅이 매 턴 끝에 등록을 재작성하므로 mtime = 마지막 활동.
# SessionsDir 이 없는 프로젝트(=그 훅이 없음)면 빈 표를 돌려 전부 '죽은듯'으로 뜬다(무해).
function Get-SessionHeartbeat([string]$main) {
  $h = @{}
  if (-not $script:SessionsDir) { return $h }
  $dir = Join-Path $main $script:SessionsDir
  if (-not (Test-Path $dir)) { return $h }
  foreach ($f in (Get-ChildItem $dir -Filter *.json -ErrorAction SilentlyContinue)) {
    try { $cwd = (Get-Content $f.FullName -Raw | ConvertFrom-Json).cwd } catch { continue }
    if (-not $cwd) { continue }
    $k = ($cwd -replace '/', '\').TrimEnd('\')
    if (-not $h.ContainsKey($k) -or $h[$k] -lt $f.LastWriteTime) { $h[$k] = $f.LastWriteTime }
  }
  return $h
}

# 브랜치가 더한 '내용'이 main 에 실제로 들어갔는지 — 커밋 개수가 아니라 **제목**으로 본다.
#
# 왜 필요한가 (2026-07-27 실측): PR 을 squash 로 머지하면 커밋이 하나로 합쳐지며 patch-id 가
# 바뀐다. 그래서 `rev-list --count origin/main..<branch>` 도 `git cherry` 도 **이미 머지된
# 브랜치를 "미반영"이라고 답한다.** 그날 미반영으로 뜬 커밋 11개가 전부 이미 머지된 것이었다.
# squash 는 제목을 그대로 두고 뒤에 " (#123)" 만 붙이므로 제목 전체 일치로 잡힌다.
# 줄 단위 비교는 안 쓴다: 오래된 브랜치는 머지 뒤 그 자리가 리팩터돼 애매한 값이 나온다.
function Get-BranchLanded([string]$branch) {
  $subs = @(& git --no-optional-locks log --format='%s' --no-merges "origin/$($script:MainBr)..$branch" 2>$null |
            Where-Object { $_ })
  if ($subs.Count -eq 0) { return $null }
  $hit = 0
  foreach ($s in $subs) {
    if (@(& git --no-optional-locks log --format='%h' -1 --fixed-strings --grep=$s "origin/$($script:MainBr)" 2>$null).Count -gt 0) { $hit++ }
  }
  return [pscustomobject]@{ total = $subs.Count; present = $hit }
}

function Get-WorktreeEntries {
  $entries = @(); $e = $null
  foreach ($line in (& git worktree list --porcelain 2>$null)) {
    if     ($line -like 'worktree *')            { if ($e) { $entries += $e }; $e = [ordered]@{ path = $line.Substring(9); branch = $null } }
    elseif ($line -like 'branch refs/heads/*')   { $e.branch = $line.Substring(18) }
  }
  if ($e) { $entries += $e }
  return $entries
}

# 잔해 = 폴더는 있는데 worktree 등록이 없는 것(옛 사고의 흔적: `.git` 만 사라진 폴더).
# **두 곳을 다 본다** — Resolve-WorktreePath 와 같은 이유다(new/start 는 ../<WtDir>/,
# Claude Code 의 EnterWorktree 는 <repo>/.claude/worktrees/). ../<WtDir>/ 만 보던 탓에
# 후자의 잔해가 목록에 아예 안 떴고, 82MB 가 쌓인 걸 사람이 폴더를 직접 열어보고서야
# 찾았다(2026-08-06, 5개). 어디 있는지 알아야 지우므로 위치(label)도 같이 준다.
# ★list 와 prune 이 **같은 판정**을 쓰게 함수로 뺐다 — 예전엔 list 가 표시만 하고
#   prune 은 `git worktree list` 등록 항목만 후보로 골라, 잔해가 영구 잔류했다.
# $seen = 정규화 경로(대문자 구분 없음) → $true. 파일은 대상이 아니다(-Directory).
function Get-StaleFolders([string]$main, $seen) {
  $roots = @(
    @{ path = (Join-Path (Split-Path $main -Parent) $script:WtDir); label = $script:WtDir },
    @{ path = (Join-Path $main '.claude\worktrees');                label = '.claude' }
  )
  $out = @()
  foreach ($r in $roots) {
    if (-not (Test-Path $r.path)) { continue }
    foreach ($d in (Get-ChildItem $r.path -Directory -ErrorAction SilentlyContinue)) {
      if ($seen.ContainsKey($d.FullName.TrimEnd('\'))) { continue }
      $out += [pscustomobject]@{ path = $d.FullName.TrimEnd('\'); label = $r.label }
    }
  }
  return $out
}

# ── list ─────────────────────────────────────────────────────────────────────
# **삭제하지 않는다** — 사람이 보고 clean 을 고른다.
function Invoke-List {
  $main = (Resolve-Path (Get-MainRoot)).Path.TrimEnd('\')
  $hb   = Get-SessionHeartbeat $main
  $now  = Get-Date
  # 판정이 전부 origin/main 기준이라 낡으면 그대로 오답. 실패는 무시(옛 ref 로 진행).
  $fresh = Update-OriginMainBestEffort

  $rows = @(); $seen = @{}
  foreach ($w in (Get-WorktreeEntries)) {
    $p = ($w.path -replace '/', '\').TrimEnd('\')
    $seen[$p] = $true
    $name  = if ($p -ieq $main) { '(main checkout)' } else { Split-Path $p -Leaf }
    $beat  = if ($hb.ContainsKey($p)) { $hb[$p] } else { $null }
    $ageM  = if ($beat) { [int]((New-TimeSpan -Start $beat -End $now).TotalMinutes) } else { $null }
    $state = if ($null -ne $ageM -and $ageM -lt $script:StaleMin) { '살아있음' } else { '죽은듯' }
    $dirty = try { @(Get-GitLinesInPath $p status --porcelain).Count } catch { '?' }
    $ahead = if ($w.branch) { [int](Get-GitValue rev-list --count "origin/$($script:MainBr)..$($w.branch)") } else { 0 }
    $landed = if ($ahead -gt 0 -and $w.branch) { Get-BranchLanded $w.branch } else { $null }   # 비싸다 — 필요할 때만
    $verdict =
      if ($ahead -eq 0)          { '' }
      elseif ($null -eq $landed) { '?' }
      elseif ($landed.present -eq $landed.total) { '이미 반영' }
      elseif ($landed.present -eq 0)             { '진짜 미반영' }
      else { "부분 $($landed.present)/$($landed.total)" }
    $br = $w.branch ?? 'detached'
    if ($br.Length -gt 24) { $br = $br.Substring(0, 23) + '…' }   # 콘솔이 좁으면 뒤쪽 칸이 통째로 날아간다
    $rows += [pscustomobject]@{
      상태 = $state; 이름 = $name; 브랜치 = $br
      미커밋 = $dirty; 커밋 = $ahead; 반영 = $verdict
      활동 = if ($null -ne $ageM) { "${ageM}분" } else { '—' }
    }
  }

  # 잔해(위 Get-StaleFolders — prune 과 같은 판정). 여기선 파일 수를 세지 않는다:
  # list 는 매번 도는 명령이라 재귀 스캔을 넣으면 느려진다. 그건 prune 에서만.
  foreach ($s in (Get-StaleFolders $main $seen)) {
    $rows += [pscustomobject]@{ 상태='잔해'; 이름=(Split-Path $s.path -Leaf); 브랜치="(.git 없음 · $($s.label))"
                                미커밋='?'; 커밋='?'; 반영='?'; 활동='—' }
  }

  $order = @{ '살아있음' = 0; '죽은듯' = 1; '잔해' = 2 }
  # Out-String -Width 없이 Format-Table 만 쓰면 콘솔이 좁을 때 뒤쪽 칸을 통째로 버린다.
  $rows | Sort-Object { $order[$_.상태] }, 이름 | Format-Table -AutoSize | Out-String -Width 200 | Write-Host

  if (-not $script:SessionsDir) { Write-Host "(이 프로젝트엔 세션 하트비트 훅이 없어 '상태'는 판정 불가 — 전부 '죽은듯')" -ForegroundColor DarkGray }
  Write-Host "커밋 = ancestry 상 origin/$($script:MainBr) 에 없는 커밋 수 — squash 머지면 부풀려 보인다(믿지 말 것)" -ForegroundColor DarkGray
  Write-Host "반영 = 브랜치가 더한 내용이 main 에 실제로 있나. '이미 반영'이면 지워도 잃을 게 없다" -ForegroundColor DarkGray
  if (-not $fresh) {
    if ($script:OriginMainUpdateSkipped) {
      Write-Host "Codex sandbox 안에서는 .git 쓰기(fetch)를 건너뛰었다. 삭제 적용은 승인/사용자 권한에서만." -ForegroundColor DarkYellow
    }
    else {
      Write-Host "⚠ origin/$($script:MainBr) 갱신 실패로 오래된 로컬 ref 기준일 수 있다. 삭제 적용은 승인/사용자 권한에서만." -ForegroundColor DarkYellow
    }
  }
  Write-Host "정리는 사람이:  $($script:CleanHint)" -ForegroundColor Green
}

# ── clean ────────────────────────────────────────────────────────────────────
function Invoke-Clean($extra) {
  $extra = @($extra)
  $force = ($extra -contains '--force') -or ($extra -contains '-f')
  $name  = [string](@($extra | Where-Object { $_ -notlike '-*' })[0])
  if (-not $name) { throw "이름 필요: clean <name> [--force]" }
  $main = Get-MainRoot
  $wt   = Resolve-WorktreePath $name $main
  if (-not (Test-Path $wt)) { throw "없음: $wt" }
  # 브랜치도 조립하지 말고 실제로 체크아웃된 것을 쓴다 — worktree 이름과 브랜치명이
  # 같다는 보장이 없다(EnterWorktree 로 만든 agent-desc 의 브랜치는 fix/agent-descriptions).
  # remove 하면 목록에서 사라지므로 **먼저** 잡아둔다.
  $entry = Get-WorktreeEntries | Where-Object { $_.path -eq ($wt -replace '\\', '/') } | Select-Object -First 1
  $br    = if ($entry -and $entry.branch) { $entry.branch } else { Get-BranchName $name }
  # ★dirty 검사를 **아무것도 지우기 전에** — prune(아래)이 쓰는 것과 같은 판정을 그대로.
  #   prune 만 이 판정을 쓰고 clean 은 안 썼다. 12h 조용함 게이트는 여기 넣지 않는다 —
  #   clean 은 사람이 이름을 찍어 부르는 명시적 행동이고 'PR 머지 직후 회수'가 정상 흐름이다.
  if (-not $force) {
    $dirty = @(Get-GitLinesInPath $wt status --porcelain)
    if ($dirty) {
      $dirty | Select-Object -First 10 | ForEach-Object { Write-Host "  $_" }
      if ($dirty.Count -gt 10) { Write-Host "  … 외 $($dirty.Count - 10) 개" }
      throw "미커밋 변경 $($dirty.Count) 개 — $wt`n  커밋하거나, 버려도 되면: clean $name --force"
    }
  }
  Remove-LegacyLinks $wt                                   # ★반드시 remove 앞에
  foreach ($f in $script:Provision) { Remove-Item (Join-Path $wt $f) -ErrorAction SilentlyContinue }
  # ★거부당하면 **멈춘다**. 옛 코드는 거부 이유를 경고 한 줄로 흘리고 곧장 --force 로 승격했다 —
  #   git 이 거부하는 건 이유가 있을 때다(미커밋·잠금·submodule). 밀 판단은 사람이 --force 로 한다.
  $rc = if ($force) { Invoke-GitShow worktree remove --force $wt } else { Invoke-GitShow worktree remove $wt }
  if ($rc -ne 0) {
    Add-Provision $wt $main    # 살아남은 worktree 를 쓸 수 있게 되돌린다(.env 없으면 import 부터 실패)
    throw "worktree remove 거부 (위 git 메시지가 이유) — 확인 후 밀려면: clean $name --force"
  }
  # 브랜치를 안 지우면 영원히 쌓인다(2026-07-28: 로컬 74·원격 121). -d 라 미머지는 git 이 거부.
  if ((Invoke-GitShow @('branch', '-d', $br)) -ne 0) {
    Write-Host "제거됨: $wt  (브랜치 $br 은 미머지라 남김 — 확실하면 git branch -D $br)"
  }
  else { Write-Host "제거됨: $wt  + 브랜치 $br" }
}

# `git status --porcelain` 한 줄이 **버려도 되는 파생물**인가.
#
# 2026-08-16 실측: `dev cp <이름>` 으로 만든 worktree 는 claude 가 뜨는 순간
# SessionStart 훅(memory-mirror)이 `docs/_ai/memory/` 를 써서 **태어나자마자 dirty** 가 된다
# (신규 worktree 2개 모두 19건). 그래서 모든 worktree 가 아래 dirty 가드에 걸려
# **자동 정리 대상이 될 수 없었다** — 12h 게이트를 넘겨도 영원히 남는다.
# 하네스 phase 산출물도 같은 성격이다(2026-08-13: dirty 9개 중 8개가 그것이라 prune 이
# 늘 "정리 대상 0" 을 반환했다). 둘 다 원본이 따로 있는 파생물이라 버려도 된다.
function Test-DerivedPath([string]$PorcelainLine) {
  if (-not $script:DerivedPaths -or @($script:DerivedPaths).Count -eq 0) { return $false }
  if ($PorcelainLine.Length -le 3) { return $false }
  $rel = $PorcelainLine.Substring(3)
  $rel = ($rel -split ' -> ')[-1]          # rename(`R  old -> new`) 은 뒤쪽이 현재 경로
  $rel = $rel -replace '^"|"$', ''          # quotepath 로 따옴표가 붙은 경우
  foreach ($d in $script:DerivedPaths) { if ($rel -like "$d*") { return $true } }
  return $false
}

# ── prune ────────────────────────────────────────────────────────────────────
# origin/main 에 고유 커밋이 없는(=빈 세션 or 완전 병합) worktree/브랜치를 정리. 기본 dry-run.
# 미병합 커밋이 있거나 dirty 하거나 최근 활동이 있으면 절대 건드리지 않는다.
function Invoke-Prune($extra) {
  $apply = ($extra -contains '--apply') -or ($extra -contains '-y')
  $now   = ($extra -contains '--now')     # 조용함 게이트 무시(사람이 판단할 때)
  $main  = (Resolve-Path (Get-MainRoot)).Path.TrimEnd('\', '/')
  $cur   = Get-GitValue rev-parse --show-toplevel
  if ($cur) { $cur = (Resolve-Path $cur).Path.TrimEnd('\', '/') }

  $fresh = Update-OriginMainBestEffort
  if ($apply -and -not $fresh) {
    if ($script:OriginMainUpdateSkipped) {
      throw "Codex sandbox 조회 모드 — .git 쓰기(fetch) 없이 삭제 적용은 하지 않는다. 사용자 PowerShell 또는 승인 경로에서 다시 실행."
    }
    throw "origin/$($script:MainBr) 갱신 실패 — stale 기준으로 삭제 적용은 하지 않는다. 사용자 권한/승인 경로에서 다시 실행."
  }
  $entries = Get-WorktreeEntries
  $prune = @(); $keep = @(); $skip = @()

  # 잔해 폴더(.git 없음) — 등록이 없으니 `git worktree list` 만 보던 옛 코드는 영구히 못 지웠다.
  $seen = @{}
  foreach ($w in $entries) { $seen[($w.path -replace '/', '\').TrimEnd('\')] = $true }
  $stale = @(Get-StaleFolders $main $seen | Where-Object {
    ($_.path -ine $main) -and (-not ($cur -and ($_.path -ieq $cur)))
  } | ForEach-Object {
    # git 이 못 되살리는 폴더다(.git 없음). 사람이 숫자를 보고 판단하도록 파일 수를 센다.
    $files = @(Get-ChildItem $_.path -Recurse -File -Force -ErrorAction SilentlyContinue).Count
    [pscustomobject]@{ path = $_.path; label = $_.label; files = $files }
  })

  foreach ($w in $entries) {
    $pN = try { (Resolve-Path $w.path -ErrorAction Stop).Path.TrimEnd('\', '/') } catch { $w.path.TrimEnd('\', '/') }
    if ($pN -ieq $main) { continue }                                          # main checkout — 절대 제외
    if ($cur -and ($pN -ieq $cur)) { $skip += @{ w=$w; why='현재 세션' }; continue }
    if (-not (Test-Path $w.path))  { $prune += @{ w=$w; ahead=0; note='경로 없음(관리항목만)' }; continue }
    # ★조용함 게이트를 status 보다 먼저 — `git status` 는 index 를 리프레시해 mtime 을 현재로
    #   만든다. 순서가 반대면 전부 '방금 활동'이 되어 아무것도 정리되지 않는다.
    if (-not $now) {
      try { $gd = Get-GitValueInPath $w.path rev-parse --absolute-git-dir }
      catch { $skip += @{ w=$w; why="gitdir 판정 실패: $_" }; continue }
      $idx = if ($gd) { Join-Path $gd 'index' } else { $null }
      # fail-closed: 판정 근거를 못 구하면 지우지 않는다(옛 코드는 실패 시 0 으로 떨어져 삭제 쪽으로 기울었다).
      if (-not $idx -or -not (Test-Path $idx)) { $skip += @{ w=$w; why='index 없음(판정 불가)' }; continue }
      $ageH = [int]((New-TimeSpan -Start (Get-Item $idx).LastWriteTime -End (Get-Date)).TotalHours)
      if ($ageH -lt $script:QuietH) { $skip += @{ w=$w; why="활동 ${ageH}h 전 (<$($script:QuietH)h)" }; continue }
    }
    try { $dirtyAll = @(Get-GitLinesInPath $w.path status --porcelain) }
    catch { $skip += @{ w=$w; why="status 판정 실패: $_" }; continue }
    # 파생물은 dirty 로 세지 않는다(위 Test-DerivedPath). 몇 건을 무시했는지는 반드시
    # 노트에 남긴다 — 조용히 버리면 "깨끗했다" 로 읽혀 다음 사람이 판정을 못 뒤집는다.
    $derivedN = @($dirtyAll | Where-Object { Test-DerivedPath $_ }).Count
    $dirty    = @($dirtyAll | Where-Object { -not (Test-DerivedPath $_) })
    if ($dirty) { $skip += @{ w=$w; why="dirty(미커밋 변경 $($dirty.Count)개)" }; continue }
    $dNote = if ($derivedN) { " · 파생물 ${derivedN}건 무시" } else { '' }
    $rev   = if ($w.branch) { $w.branch } else { Get-GitValueInPath $w.path rev-parse HEAD }
    $ahead = [int](Get-GitValue rev-list --count "origin/$($script:MainBr)..$rev")
    if ($ahead -eq 0) { $prune += @{ w=$w; ahead=0; note=$(if ($w.branch) { '병합/빈 세션' } else { 'detached(병합됨)' }) + $dNote } }
    else {
      $landed = Get-BranchLanded $rev
      if ($landed -and $landed.present -eq $landed.total) {
        $prune += @{ w=$w; ahead=$ahead; note="이미 반영(제목 $($landed.present)/$($landed.total) main 에 있음 · ahead $ahead)$dNote" }
      }
      elseif ($landed -and $landed.present -gt 0) {
        $keep += @{ w=$w; ahead=$ahead; note="부분 반영 $($landed.present)/$($landed.total)" }   # 사람이 봐야 함
      }
      else { $keep += @{ w=$w; ahead=$ahead } }
    }
  }

  # worktree 없이 남은 브랜치 — 누적의 본체(어떤 경로로도 안 지워지던 것들).
  # ★ahead 0 만 보면 squash 머지된 것이 전부 남는다(ahead 1~9 로 뜬다) — Get-BranchLanded 로
  #   제목이 전부 main 에 있는지까지 본다. 부분 반영·판정불가($null)는 사람이 봐야 하니 남긴다.
  # ★판정을 --apply 체크보다 **앞**에 둔다 — 예전엔 apply 뒤에 있어 dry-run 에 안 보였고,
  #   사람이 무엇이 지워질지 모른 채 --apply 를 눌러야 했다.
  $wtBranches = @($entries | ForEach-Object { $_.branch } | Where-Object { $_ })
  $refs    = if ($script:SweepRefs) { $script:SweepRefs } else { @('refs/heads') }
  # ★안 지우는 고아도 $orphanKeep 에 담아 '유지' 에 찍는다 — **표시만**이다.
  #   안 보이면 다음 사람이 같은 브랜치를 또 판다(2026-08-17: wip/order-book-month 가
  #   어느 구역에도 안 나와, 왜 안 지워졌는지를 손으로 다시 재야 했다).
  $orphans = @(); $orphanKeep = @()
  foreach ($b in (& git for-each-ref --format='%(refname:short)' @refs 2>$null)) {
    if ($b -eq $script:MainBr -or ($wtBranches -contains $b)) { continue }
    $bAhead = [int](Get-GitValue rev-list --count "origin/$($script:MainBr)..$b")
    if ($bAhead -eq 0) { $orphans += @{ branch=$b; ahead=0; note='병합됨' }; continue }
    $landed = Get-BranchLanded $b
    if ($landed -and $landed.present -eq $landed.total) {
      $orphans += @{ branch=$b; ahead=$bAhead; note="이미 반영(제목 $($landed.present)/$($landed.total) · ahead $bAhead)" }
    }
    elseif ($null -eq $landed)      { $orphanKeep += @{ branch=$b; note="판정 불가 (ahead $bAhead)" } }
    elseif ($landed.present -eq 0)  { $orphanKeep += @{ branch=$b; note="진짜 미반영 (제목 0/$($landed.total) · ahead $bAhead)" } }
    else                            { $orphanKeep += @{ branch=$b; note="부분 $($landed.present)/$($landed.total) (ahead $bAhead)" } }
  }

  Write-Host ""
  Write-Host "── 정리 대상 (고유 커밋 0 또는 이미 반영) ──" -ForegroundColor Yellow
  if (-not $fresh) {
    if ($script:OriginMainUpdateSkipped) {
      Write-Host "  Codex sandbox 조회 모드 — 기존 로컬 origin/$($script:MainBr) 기준의 dry-run" -ForegroundColor DarkYellow
    }
    else {
      Write-Host "  ⚠ origin/$($script:MainBr) 갱신 실패 — 기존 로컬 ref 기준의 dry-run" -ForegroundColor DarkYellow
    }
  }
  if (-not $prune) { Write-Host "  (없음)" }
  foreach ($x in $prune) { Write-Host ("  {0}  [{1}]  {2}" -f $x.w.path, ($x.w.branch ?? 'detached'), $x.note) }
  Write-Host ""
  Write-Host "── 잔해 폴더 (.git 없음 — git 이 못 되살린다) ──" -ForegroundColor Yellow
  if (-not $stale) { Write-Host "  (없음)" }
  foreach ($x in $stale) { Write-Host ("  {0}  [{1}]  파일 {2}개" -f $x.path, $x.label, $x.files) }
  Write-Host ""
  Write-Host "── 고아 브랜치 (워크트리 없음) ──" -ForegroundColor Yellow
  if (-not $orphans) { Write-Host "  (없음)" }
  foreach ($x in $orphans) { Write-Host ("  {0}  {1}" -f $x.branch, $x.note) }
  Write-Host ""
  Write-Host "── 유지 (미병합 커밋 있음 — 손대지 않음) ──" -ForegroundColor Cyan
  if (-not $keep -and -not $orphanKeep) { Write-Host "  (없음)" }
  foreach ($x in $keep) {
    Write-Host ("  {0}  [{1}]  ahead {2}{3}" -f $x.w.path, $x.w.branch, $x.ahead, $(if ($x.note) { "  ← $($x.note)" } else { '' }))
  }
  foreach ($x in $orphanKeep) { Write-Host ("  {0}  [고아]  {1}" -f $x.branch, $x.note) }
  if ($skip) {
    Write-Host ""; Write-Host "── 건너뜀 ──"
    foreach ($x in $skip) { Write-Host ("  {0}  ({1})" -f $x.w.path, $x.why) }
  }
  Write-Host ""

  if (-not $apply) {
    if ($now) { Write-Host "⚠ --now: 조용함 게이트 무시 — 방금 push 한 활성 세션도 대상에 든다. 다른 세션이 안 돌 때만." -ForegroundColor DarkYellow }
    else      { Write-Host "활동 $($script:QuietH)h 이내 worktree 는 자동 제외(활성 세션 보호). 무시하려면 --now." -ForegroundColor DarkGray }
    Write-Host "[DRY RUN] 실제 정리하려면 뒤에 --apply" -ForegroundColor Green
    return
  }

  $n = 0
  foreach ($x in $prune) {
    $w = $x.w
    if (Test-Path $w.path) {
      Remove-LegacyLinks $w.path                            # ★재귀 삭제 전에 링크부터
      foreach ($f in $script:Provision) { Remove-Item (Join-Path $w.path $f) -ErrorAction SilentlyContinue }
      if ((Invoke-GitShow worktree remove $w.path) -ne 0) { Invoke-GitShow worktree remove --force $w.path | Out-Null }
    }
    # ★SHA 를 먼저 찍는다 — 지운 걸 되살릴 수 있어야 한다:
    #   git branch <name> <sha>  ·  git push origin <sha>:refs/heads/<name>
    $sha = if ($w.branch) { Get-GitValue rev-parse --short=8 $w.branch } else { '' }
    # ★main 은 지우지 않는다 — worktree 가 main 을 체크아웃한 채 방치되면 여기로 딸려 들어온다.
    #   (2026-08-01 실측: `store-sale-apply` 가 main 을 물고 있어 **로컬 main 이 삭제**됐다.
    #    origin/main 조상이라 잃은 커밋은 0 이었지만, 로컬 main 이 없으면 SessionStart 의
    #    ff 훅이 침묵해 다음 세션들이 stale base 로 출발한다 — 쌍둥이 커밋의 뿌리다.)
    #   아래 고아 쓸기에는 이미 같은 가드가 있었는데 이 줄만 빠져 있었다.
    # 배열 splat: 싱글대시 -D 가 파라미터로 파싱되는 것 방지.
    if ($w.branch -and $w.branch -ne $script:MainBr) { Invoke-GitShow @('branch', '-D', $w.branch) | Out-Null }
    Write-Host ("제거: {0}  [{1} {2}]  {3}" -f $w.path, ($w.branch ?? 'detached'), $sha, $x.note)
    $n++
  }

  # 잔해 폴더는 등록이 없으니 `git worktree remove` 가 안 먹는다 — 폴더째 지운다.
  foreach ($x in $stale) {
    Remove-LegacyLinks $x.path                                # ★재귀 삭제 전에 링크부터
    Remove-Item $x.path -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host ("제거(잔해): {0} · 파일 {1}개" -f $x.path, $x.files)
    $n++
  }

  # 고아 브랜치(위에서 판정한 것만 지운다).
  foreach ($x in $orphans) {
    $bsha = Get-GitValue rev-parse --short=8 $x.branch
    Invoke-GitShow @('branch', '-D', $x.branch) | Out-Null
    Write-Host "브랜치 삭제(고아·$($x.note)): $($x.branch) $bsha"
    $n++
  }

  Invoke-GitShow worktree prune | Out-Null
  Write-Host ""
  Write-Host "정리 완료: $n 개" -ForegroundColor Green
}

# ── 진입점 ───────────────────────────────────────────────────────────────────
function Invoke-Wt {
  param([hashtable]$Config, [string]$Command, $Rest)
  $script:WtDir        = $Config.WtDir
  $script:BranchPrefix = [string]$Config.BranchPrefix
  $script:Provision    = @($Config.Provision)
  $script:SessionsDir  = $Config.SessionsDir
  $script:SweepRefs    = @($Config.SweepRefs)
  $script:CleanHint    = $Config.CleanHint
  $script:MainBr       = if ($Config.MainBranch) { $Config.MainBranch } else { 'main' }
  # ★버려도 되는 파생물 — prune 의 dirty 판정에서 제외한다(아래 Test-DerivedPath).
  #   레포가 Config.DerivedPaths 로 덮어쓸 수 있다. 경로는 git 표기(`/`)에 접두 매칭.
  #   ⛔`.dev/plans/` 는 정본이니 절대 넣지 마라 — 사람이 회수해야 하는 계획 문서다.
  $script:DerivedPaths = if ($null -ne $Config.DerivedPaths) { @($Config.DerivedPaths) }
                         else { @('docs/_ai/memory/', '.dev/harness/phases/') }
  $label               = $Config.Label
  # ★배열로 정규화. $Rest 가 스칼라 문자열로 들어오면 $Rest[0] 이 **첫 글자**를 집는다
  #   ('engine-test' → 'e' 로 worktree 가 만들어졌다, 2026-07-28 실측). 위치 인자로 부르면
  #   ValueFromRemainingArguments 가 배열을 주지만, -Rest 로 직접 넘기면 스칼라다.
  $Rest = @($Rest)

  switch ($Command) {
    'new'        { Invoke-New       ([string]$Rest[0]) }
    'start'      { Invoke-Start     ([string]$Rest[0]) ($Rest | Select-Object -Skip 1) }
    'provision'  { Invoke-Provision ([string]$Rest[0]) }
    'land'       { Invoke-Land }
    'prune'      { Invoke-Prune     ($Rest) }
    'list'       { Invoke-List }
    { $_ -in 'clean', 'rm' } { Invoke-Clean ($Rest) }   # rm = Coupang 쪽 옛 이름
    default {
      Write-Host "$label worktree — 세션 격리"
      Write-Host "  start <name>      ★권장: worktree 생성/재사용 + provision + claude 실행"
      Write-Host "  new <name>        생성 + provision (수동 cd)"
      Write-Host "  provision [path]  현재/지정 worktree 에 설정파일 복사"
      Write-Host "  land              origin/$($script:MainBr) 에 rebase (push 는 수동)"
      Write-Host "  list              현황 (삭제 안 함)"
      Write-Host "  clean|rm <name>   제거 (+머지된 브랜치) · --force = 미커밋 있어도 밀기"
      Write-Host "  prune [--apply]   일괄 정리 (기본 dry-run · --now = 조용함게이트 무시)"
      if ($Command) { throw "알 수 없는 명령: $Command" }
    }
  }
}
