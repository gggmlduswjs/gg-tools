# install.ps1 — 이 PC 에 claude 레포를 배선한다(멱등).
#   새 PC:  gh repo clone gggmlduswjs/claude ~\claude ;  pwsh ~\claude\install.ps1 ;  새 터미널
#   -Force = 이미 있는 ~\.claude 파일도 덮어씀(기본은 안 건드림 — 그 PC 설정을 날리지 않는다)
#
# 무엇이 심링크이고 무엇이 복사인가:
#   심링크 = 한 벌만 존재해야 하는 것(CLAUDE.md·skills·agents). 어느 PC에서 고쳐도 같은 파일.
#   복사   = Claude Code 가 자주 덮어쓰거나 PC 마다 달라야 하는 것(settings.json 의
#            permissions.allow 는 경로별). 심링크면 레포가 늘 dirty 하고 PC 끼리 충돌한다.
param([switch]$Force)
$ErrorActionPreference = 'Stop'
$repo   = $PSScriptRoot
$dotcl  = Join-Path $env:USERPROFILE '.claude'
$sync   = 'G:\내 드라이브\claude-sync'      # 메모리 전용(두 PC append — git 으로는 매번 충돌)
$marker = '# >>> dotfiles dev launcher >>>'  # ★그대로 둔다 — 배선 여부 판정 열쇠. 바꾸면 중복 배선된다

function Set-Link($link, $target) {
  if (-not (Test-Path $target)) { Write-Host "  [skip] 대상 없음: $target" -Fore Yellow; return }
  $cur = if (Test-Path $link) { (Get-Item $link -Force).Target } else { $null }
  if ($cur -eq $target) { Write-Host "  [ok]   $(Split-Path $link -Leaf)" -Fore DarkGray; return }
  if (Test-Path $link) {
    $bak = "$link.bak"
    if (Test-Path $bak) { Remove-Item $bak -Recurse -Force }
    Move-Item $link $bak
    Write-Host "  [백업] $(Split-Path $link -Leaf) -> .bak" -Fore Yellow
  }
  New-Item -ItemType Directory -Force (Split-Path $link) | Out-Null
  New-Item -ItemType SymbolicLink -Path $link -Target $target | Out-Null
  Write-Host "  [link] $(Split-Path $link -Leaf)" -Fore Green
}

function Set-Copy($src, $dst) {
  if (-not (Test-Path $src)) { return }
  $name = Split-Path $dst -Leaf
  if ((Test-Path $dst) -and -not $Force) { Write-Host "  [유지] $name (이 PC 설정 — -Force 로 덮어씀)" -Fore DarkGray; return }
  New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
  Copy-Item $src $dst -Force
  Write-Host "  [copy] $name" -Fore Green
}

# ── 1) PowerShell 프로필에 dev 런처 배선 ────────────────────────────────
Write-Host "`n== 프로필 ==" -Fore Cyan
$dev = Join-Path $repo 'powershell\dev-profile.ps1'
if (-not (Test-Path $dev)) { throw "본체 없음: $dev (clone 확인)" }
$dir = Split-Path $PROFILE -Parent
if (-not (Test-Path $dir))     { New-Item -ItemType Directory -Force $dir | Out-Null }
if (-not (Test-Path $PROFILE)) { New-Item -ItemType File -Force $PROFILE | Out-Null }

$content = Get-Content $PROFILE -Raw -ErrorAction SilentlyContinue
$wired = $false
if ($content -and $content.Contains($marker)) {
  # 배선돼 있어도 가리키는 파일이 없으면 옛 경로다(dotfiles→claude 개명 등). 블록째 걷어낸다.
  if ($content -match [regex]::Escape($dev)) {
    Write-Host "  [ok]   이미 배선됨" -Fore DarkGray; $wired = $true
  } else {
    $pat = [regex]::Escape($marker) + '.*?# <<< dotfiles dev launcher <<<'
    Set-Content $PROFILE ([regex]::Replace($content, $pat, '', 'Singleline').TrimEnd())
    Write-Host "  [갱신] 옛 배선 제거 — 경로가 바뀌었다" -Fore Yellow
  }
}
if (-not $wired) {
  Add-Content $PROFILE "`n$marker`n. `"$dev`"`n# <<< dotfiles dev launcher <<<`n"
  Write-Host "  [배선] $PROFILE  → 새 터미널에서 'dev bm' / '현황' 사용 가능" -Fore Green
}

# ── 2) ~/.claude 배치 ───────────────────────────────────────────────────
Write-Host "`n== ~/.claude ==" -Fore Cyan
Set-Link (Join-Path $dotcl 'CLAUDE.md') (Join-Path $repo 'home\CLAUDE.md')
Set-Link (Join-Path $dotcl 'skills')    (Join-Path $repo 'home\skills')
Set-Link (Join-Path $dotcl 'agents')    (Join-Path $repo 'home\agents')
Set-Copy (Join-Path $repo 'home\settings.json')       (Join-Path $dotcl 'settings.json')
Set-Copy (Join-Path $repo 'home\statusline.ps1')      (Join-Path $dotcl 'statusline.ps1')
Set-Copy (Join-Path $repo 'home\understand-any.ps1')  (Join-Path $dotcl 'understand-any.ps1')

# ── 3) 프로젝트별 편집기 설정 ───────────────────────────────────────────
# .vscode/ 는 두 레포 다 gitignore 라 PC 를 옮기면 사라진다. 그런데 files.exclude
# (탐색기에서 캐시·빌드·생성물 숨기기)는 PC 마다 다시 만들 이유가 없는 설정이다.
# 여기에 정본을 두고 배치한다. 기존 파일은 안 덮는다(그 PC 에서 손본 걸 날리면 안 된다).
Write-Host "`n== 프로젝트 편집기 설정 ==" -Fore Cyan
$base = if ($env:DEV_PROJECTS) { $env:DEV_PROJECTS } else { Join-Path $env:USERPROFILE 'Desktop' }
$projSrc = Join-Path $repo 'projects'
if (Test-Path $projSrc) {
  foreach ($p in (Get-ChildItem $projSrc -Directory)) {
    $dstRoot = Join-Path $base $p.Name
    if (-not (Test-Path $dstRoot)) { Write-Host "  [skip] 레포 없음: $($p.Name)" -Fore Yellow; continue }
    Write-Host "  $($p.Name)" -Fore DarkCyan
    foreach ($f in (Get-ChildItem $p.FullName -Recurse -File)) {
      $rel = $f.FullName.Substring($p.FullName.Length).TrimStart('\')
      Set-Copy $f.FullName (Join-Path $dstRoot $rel)
    }
  }
}

# ── 4) 메모리 심링크 ────────────────────────────────────────────────────
# 프로젝트별 memory 는 Drive 에 둔다 — 두 PC 가 각자 append 하는 누적물이라 git 이면 파일마다 충돌한다.
# (워크트리 세션의 memory 는 settings.json 의 SessionStart 훅이 그때그때 걸어준다)
Write-Host "`n== 메모리 ==" -Fore Cyan
$u = $env:USERNAME
$map = @{
  "C--Users-$u-Desktop-bookmart"   = 'bookmart-memory'
  "C--Users-$u-Desktop-Coupang-v2" = 'coupang-v2-memory'
  "C--Users-$u-Desktop-Coupong"    = 'coupong-memory'
  "C--Users-$u-Desktop-speakfit"   = 'speakfit-memory'
  'G---------Obsidian'             = 'obsidian-memory'
}
if (Test-Path $sync) {
  foreach ($h in $map.Keys) { Set-Link "$dotcl\projects\$h\memory" "$sync\$($map[$h])" }
} else {
  Write-Host "  [skip] Drive 없음: $sync (동기화 완료 후 다시 실행)" -Fore Yellow
}

# ── 4.5) git 훅 배선 ────────────────────────────────────────────────────
# .git/hooks 는 clone 에 따라오지 않는다 — 레포에 든 폴더를 가리켜야 새 PC 에서도 산다.
git -C $repo config core.hooksPath .githooks 2>$null
Write-Host "  [ok]   git hooks -> .githooks" -Fore DarkGray

# 코드 레포 둘도 같이 건다. **여기가 비어 있어서 새 PC 에 clone 하면 훅이 통째로 안 돌았다**
# (2026-08-06 발견). 이 레포는 `.githooks/`, 코드 레포는 `.claude/hooks/` 다 — 이 레포엔
# `.claude/` 폴더가 없다(자기가 그 내용물이라). 구조가 달라서 이름이 갈린 것뿐이다.
foreach ($p in @('bookmart', 'Coupang_v2')) {
  $pr = Join-Path $base $p
  if (-not (Test-Path (Join-Path $pr '.git'))) { continue }
  git -C $pr config core.hooksPath .claude/hooks 2>$null
  Write-Host "  [ok]   git hooks -> $p/.claude/hooks" -Fore DarkGray
}

# ── 5) 검증 ─────────────────────────────────────────────────────────────
# 기댓값을 숫자로 박아두면 메모리가 늘 때마다 낡아서 '성공'을 '실패'로 읽는다
# (실제로 279/148 로 박아둔 게 404/220 이 됐다). Drive 원본과 대조하면 안 낡는다.
Write-Host "`n== 검증 ==" -Fore Cyan
$ok = $true
foreach ($n in 'CLAUDE.md', 'skills') {          # 필수
  $hit = Test-Path (Join-Path $dotcl $n)
  if (-not $hit) { $ok = $false }
  Write-Host ("  {0,-12} {1}" -f $n, $(if ($hit) { 'OK' } else { 'X' })) -Fore $(if ($hit) { 'Green' } else { 'Red' })
}
# agents 는 선택 — 레포에 아직 없으면 실패가 아니다
$agentSrc = Join-Path $repo 'home\agents'
Write-Host ("  {0,-12} {1}" -f 'agents', $(if (Test-Path $agentSrc) { 'OK' } else { '— (레포에 없음)' })) -Fore DarkGray
# 점폴더는 스킬이 아니다(.git 등). 필터를 빼면 개수가 실제보다 크게 나온다
$cnt = (Get-ChildItem "$dotcl\skills" -Directory -EA SilentlyContinue | Where-Object Name -notlike '.*').Count
Write-Host ("  {0,-12} {1}종" -f 'skills', $cnt)
if (Test-Path $sync) {
  foreach ($h in $map.Keys) {
    $m = "$dotcl\projects\$h\memory"; $src = "$sync\$($map[$h])"
    $want = if (Test-Path $src) { (Get-ChildItem $src -File -Recurse -EA SilentlyContinue).Count } else { 0 }
    $got  = if (Test-Path $m)   { (Get-ChildItem $m   -File -Recurse -EA SilentlyContinue).Count } else { -1 }
    $good = ($want -gt 0 -and $got -eq $want)
    if (-not $good) { $ok = $false }
    Write-Host ("  {0,-20} {1} / {2} 원본  {3}" -f $map[$h], $got, $want, $(if ($good) { 'OK' } else { 'X' })) -Fore $(if ($good) { 'Green' } else { 'Red' })
  }
}
Write-Host ""
if ($ok) { Write-Host "완료. 새 터미널을 열면 끝." -Fore Green }
else     { Write-Host "일부 X — 위 줄을 확인. Drive 동기화(초록불) 또는 개발자 모드(심링크 권한)를 먼저." -Fore Yellow }
