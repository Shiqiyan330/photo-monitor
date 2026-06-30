$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Dist = Join-Path $Root "dist"
$PackageDir = Join-Path $Dist "photo-monitor-uploader"
$Exe = Join-Path $PackageDir "photo-monitor-uploader.exe"
$StaleDistExe = Join-Path $Dist "photo-monitor-uploader.exe"
$StaleDebugExe = Join-Path $Dist "photo-monitor-uploader-debug.exe"
$DownloadZip = Join-Path $Root "photo-monitor\public\downloads\photo-monitor-uploader.zip"
$DownloadDir = Join-Path $Root "photo-monitor\public\downloads\photo-monitor-uploader"
$StaleDownloadExe = Join-Path $Root "photo-monitor\public\downloads\photo-monitor-uploader.exe"
$TempRoot = Join-Path $Root ".photo-monitor-uploader-test"
$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }
$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

function Test-PythonForUploader {
  param([string]$Candidate)
  if (-not $Candidate) {
    return $false
  }
  $command = Get-Command $Candidate -ErrorAction SilentlyContinue
  if (-not $command) {
    return $false
  }
  & $Candidate -c "from PySide6.QtCore import qVersion; print(qVersion())" | Out-Null
  return $LASTEXITCODE -eq 0
}

function Install-UploaderRequirements {
  param([string]$Candidate)
  & $Candidate -m pip install --timeout 120 -r (Join-Path $PSScriptRoot "requirements.txt") | Out-Host
  if ($LASTEXITCODE -ne 0) {
    throw "pip install failed for $Candidate"
  }
}

function Select-PythonForUploader {
  $candidates = @($Python)
  if (-not $env:PYTHON) {
    $candidates += $BundledPython
  }
  foreach ($candidate in $candidates) {
    Install-UploaderRequirements $candidate
    if (Test-PythonForUploader $candidate) {
      return $candidate
    }
    Write-Warning "Python cannot load PySide6 QtCore: $candidate"
  }
  throw "No usable Python found. PySide6.QtCore could not be imported."
}

New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null
$env:TMP = $TempRoot
$env:TEMP = $TempRoot

$Python = Select-PythonForUploader

& $Python -m unittest uploader.test_photo_monitor_uploader uploader.test_gui_operations
if ($LASTEXITCODE -ne 0) {
  throw "unit tests failed"
}

$PythonExe = (Get-Command $Python).Source
$PythonRoot = Split-Path $PythonExe -Parent
$SitePackages = (& $Python -c "import site; print(site.getsitepackages()[0])").Trim()
$BuildPath = @(
  $PythonRoot,
  (Join-Path $PythonRoot "DLLs"),
  (Join-Path $SitePackages "PySide6"),
  (Join-Path $SitePackages "shiboken6"),
  (Join-Path $env:WINDIR "System32"),
  $env:WINDIR,
  (Join-Path $env:WINDIR "System32\Wbem")
) -join ";"

$OriginalPath = $env:PATH
try {
  $env:PATH = $BuildPath
  & $Python -m PyInstaller `
    --clean `
    --noconfirm `
    --onedir `
    --windowed `
    --name photo-monitor-uploader `
    (Join-Path $PSScriptRoot "photo_monitor_uploader.py")
  if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed"
  }
} finally {
  $env:PATH = $OriginalPath
}

if (-not (Test-Path -LiteralPath $Exe)) {
  throw "Build output not found: $Exe"
}

if (Test-Path -LiteralPath $DownloadZip) {
  Remove-Item -LiteralPath $DownloadZip -Force
}
foreach ($stalePath in @($StaleDistExe, $StaleDebugExe)) {
  if (Test-Path -LiteralPath $stalePath) {
    Remove-Item -LiteralPath $stalePath -Force
  }
}
if (Test-Path -LiteralPath $DownloadDir) {
  Remove-Item -LiteralPath $DownloadDir -Recurse -Force
}
if (Test-Path -LiteralPath $StaleDownloadExe) {
  Remove-Item -LiteralPath $StaleDownloadExe -Force
}
Copy-Item -LiteralPath $PackageDir -Destination $DownloadDir -Recurse -Force
Compress-Archive -LiteralPath $PackageDir -DestinationPath $DownloadZip -Force
Write-Host "Built and packaged: $DownloadZip"
