$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Dist = Join-Path $Root "dist"
$Exe = Join-Path $Dist "photo-monitor-uploader.exe"
$DownloadExe = Join-Path $Root "photo-monitor\public\downloads\photo-monitor-uploader.exe"
$TempRoot = Join-Path $Root ".photo-monitor-uploader-test"
$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null
$env:TMP = $TempRoot
$env:TEMP = $TempRoot

& $Python -m pip install --timeout 120 -r (Join-Path $PSScriptRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
  throw "pip install failed"
}

& $Python -m unittest uploader.test_photo_monitor_uploader uploader.test_gui_operations
if ($LASTEXITCODE -ne 0) {
  throw "unit tests failed"
}

& $Python -m PyInstaller `
  --noconfirm `
  --onefile `
  --windowed `
  --name photo-monitor-uploader `
  (Join-Path $PSScriptRoot "photo_monitor_uploader.py")
if ($LASTEXITCODE -ne 0) {
  throw "PyInstaller build failed"
}

if (-not (Test-Path -LiteralPath $Exe)) {
  throw "Build output not found: $Exe"
}

Copy-Item -LiteralPath $Exe -Destination $DownloadExe -Force
Write-Host "Built and copied: $DownloadExe"
