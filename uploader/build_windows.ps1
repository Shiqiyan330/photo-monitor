$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Dist = Join-Path $Root "dist"
$Exe = Join-Path $Dist "photo-monitor-uploader.exe"
$DownloadExe = Join-Path $Root "photo-monitor\public\downloads\photo-monitor-uploader.exe"
$TempRoot = Join-Path $Root ".photo-monitor-uploader-test"

New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null
$env:TMP = $TempRoot
$env:TEMP = $TempRoot

python -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
python -m unittest uploader.test_photo_monitor_uploader

pyinstaller `
  --noconfirm `
  --onefile `
  --windowed `
  --name photo-monitor-uploader `
  (Join-Path $PSScriptRoot "photo_monitor_uploader.py")

if (-not (Test-Path -LiteralPath $Exe)) {
  throw "Build output not found: $Exe"
}

Copy-Item -LiteralPath $Exe -Destination $DownloadExe -Force
Write-Host "Built and copied: $DownloadExe"
