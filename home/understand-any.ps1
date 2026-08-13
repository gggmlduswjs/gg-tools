# 범용 "이해 현황" 런처 — 어느 프로젝트에서든 작동(현재 폴더 자동 감지).
# 유저 레벨 /현황 명령이 호출. 직접:  powershell -File understand-any.ps1 [-Proj <경로>]
param([string]$Proj = (Get-Location).Path)
try { $Proj = (Resolve-Path $Proj).Path } catch {}
# cwd가 레포 하위(예: *-course)여도 git 최상위로 올려잡기 → 항상 전체 레포를 그림
try { $g = (git -C $Proj rev-parse --show-toplevel 2>$null); if ($g) { $Proj = (Resolve-Path $g).Path } } catch {}
$py  = "C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
$vis = "C:\Users\user\.claude\skills\codebase-visualizer\scripts\visualize.py"
function Up($p){ Test-NetConnection localhost -Port $p -InformationLevel Quiet -WarningAction SilentlyContinue }

# 1) 파일트리 맵 최신화(현재 프로젝트)
if ((Test-Path $py) -and (Test-Path $vis)) { & $py $vis $Proj *> $null }

# 2) omm: 이 프로젝트에 .omm 있으면, 경로 해시로 고정 포트(3100~3799)에 뷰어 상주
#    프로젝트마다 자기 포트 → 서로 안 죽이고 각자 살아있음.
$hasOmm = Test-Path (Join-Path $Proj ".omm")
$md5 = [System.Security.Cryptography.MD5]::Create()
$h = [BitConverter]::ToUInt16($md5.ComputeHash([Text.Encoding]::UTF8.GetBytes($Proj.ToLower())), 0)
$port = 3100 + ($h % 700)
if ($hasOmm -and -not (Up $port)) {
  Start-Process -WindowStyle Minimized -WorkingDirectory $Proj -FilePath "cmd.exe" -ArgumentList "/c","omm view --port $port"
}
Start-Sleep -Seconds 4

# 3) 열 것 모으기 — 그 폴더에 실제로 있는 것만 (DeepWiki 없음)
$open = New-Object System.Collections.ArrayList
$map = Join-Path $Proj "codebase-map.html"
if (Test-Path $map) { [void]$open.Add($map) }
if ($hasOmm)        { [void]$open.Add("http://localhost:$port") }
$air = Join-Path $Proj "docs\ai-readiness-map.html"
if (Test-Path $air) { [void]$open.Add($air) }
Get-ChildItem -Path $Proj -Directory -Filter "*-course" -ErrorAction SilentlyContinue | ForEach-Object {
  $idx = Join-Path $_.FullName "index.html"
  if (Test-Path $idx) { [void]$open.Add($idx) }
}

# 4) 파일 먼저(브라우저 웜업) → http 나중, 텀 두고 (콜드 브라우저 씹힘 방지)
$firstFile = $open | Where-Object { $_ -notlike "http*" } | Select-Object -First 1
if ($firstFile) { cmd /c start "" "$firstFile"; Start-Sleep -Seconds 3 }
foreach ($t in ($open | Where-Object { $_ -ne $firstFile })) {
  cmd /c start "" "$t"; Start-Sleep -Milliseconds 900
}

# 5) 요약
Write-Host "============ 이해 현황 ============"
Write-Host "  프로젝트: $Proj"
if ($hasOmm) { Write-Host ("  omm      :$port   " + $(if(Up $port){'ON'}else{'OFF'})) } else { Write-Host "  omm      (.omm 없음 - /omm-scan 먼저 돌리면 생김)" }
Write-Host ("  연 탭 " + $open.Count + "개 (파일트리" + $(if(Test-Path $air){'/AI준비도'}else{''}) + "/omm/강의 중 있는 것)")
Write-Host "=================================="
