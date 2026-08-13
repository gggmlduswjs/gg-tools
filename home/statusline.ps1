# Claude Code statusline — model · dir · git branch (+ ponytail badge)
$raw = [Console]::In.ReadToEnd()
try { $ctx = $raw | ConvertFrom-Json } catch { exit 0 }

$esc = [char]27
$dim = "$esc[38;5;240m"; $rst = "$esc[0m"
$mid = [char]0xB7  # middle dot (ASCII source; avoids PS 5.1 encoding corruption)

$model = $ctx.model.display_name
$dir   = if ($ctx.workspace.current_dir) { $ctx.workspace.current_dir } else { $ctx.cwd }
$leaf  = if ($dir) { Split-Path $dir -Leaf } else { "" }

$parts = @()
if ($model) { $parts += "$esc[38;5;110m$model$rst" }
if ($leaf)  { $parts += "$esc[38;5;108m$leaf$rst" }

$branch = & git -C $dir rev-parse --abbrev-ref HEAD 2>$null
if ($LASTEXITCODE -eq 0 -and $branch) { $parts += "$esc[38;5;180m$branch$rst" }

$line = $parts -join " $dim$mid$rst "

# ponytail 배지 (ponytail-statusline.ps1 로직 복제)
$base = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$flag = Join-Path $base '.ponytail-active'
if (Test-Path $flag) {
    $mode = (Get-Content $flag -First 1).Trim()
    $badge = if ([string]::IsNullOrEmpty($mode) -or $mode -eq 'full') { '[PONYTAIL]' } `
             else { "[PONYTAIL:$($mode.ToUpperInvariant())]" }
    $line += " $esc[38;5;108m$badge$rst"
}

[Console]::Write($line)
