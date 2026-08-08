#!/usr/bin/env pwsh
# statusline-wrapper.ps1 — 쓰던 상태줄 뒤에 「지금 도는 하네스」 칸을 덧붙인다.
#
# 왜 감싸나: ccstatusline 의 위젯 스키마(config version 3)를 역공학해 커스텀 칸을
# 끼우는 건 그쪽이 바뀌면 깨진다. 감싸면 **그쪽 설정을 하나도 안 건드리고**,
# 커스텀 위젯 지원 여부와 무관하게 동작한다. 쓰던 게 그대로 나온다.
#
# Claude Code 는 상태줄 명령에 **stdin 으로 JSON** 을 준다(cwd·model·session 등).
# stdin 은 한 번만 읽힌다 — 그래서 여기서 통째로 받아 안쪽 상태줄에 그대로 넘긴다.
#
# ⛔ 절대 죽지 않는다. 하네스 칸이 실패해도 **안쪽 상태줄은 그대로 나와야** 한다.
#   상태줄이 깨지면 10초마다 눈에 거슬리고, 정작 고칠 땐 원인이 안 보인다.

$ErrorActionPreference = "SilentlyContinue"

# 1) stdin 을 통째로 받는다 (JSON 한 덩어리)
$payload = [Console]::In.ReadToEnd()

# 2) 쓰던 상태줄을 그대로 돌린다
$inner = ""
try {
    $inner = ($payload | & npx -y ccstatusline@latest 2>$null | Out-String).TrimEnd()
} catch { $inner = "" }

# 3) 하네스 칸 — cwd 는 stdin JSON 에서 꺼낸다(상태줄 프로세스의 CWD 는 못 믿는다)
$harness = ""

# ⚠️ JSON 파싱은 **따로** 감싼다. 예전엔 이 아래 전체가 한 try 안에 있어서,
#    JSON 이 깨지면 바로 밑에 준비해둔 cwd 폴백까지 통째로 삼켰다 — 폴백을 두고도 안 썼다.
$cwd = $null
try {
    if ($payload) {
        $json = $payload | ConvertFrom-Json
        $cwd = $json.cwd
        if (-not $cwd) { $cwd = $json.workspace.current_dir }
    }
} catch { $cwd = $null }
if (-not $cwd) { $cwd = (Get-Location).Path }

try {
    $script = Join-Path $PSScriptRoot "harness-status.ps1"
    if (Test-Path $script) {
        $harness = (& $script -RepoRoot $cwd | Out-String).Trim()
    }
} catch { $harness = "" }

if ($harness) {
    # ANSI 노랑 — 다른 칸과 구분되게. 색이 안 먹는 호스트면 그냥 글자만 보인다.
    $sep = if ($inner) { " " + [char]27 + "[90m│" + [char]27 + "[0m " } else { "" }
    Write-Output ($inner + $sep + [char]27 + "[33m" + $harness + [char]27 + "[0m")
} else {
    Write-Output $inner
}
