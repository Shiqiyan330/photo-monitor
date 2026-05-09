$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Uploader = Join-Path $ScriptDir "local_uploader.py"
$Pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source

if (-not $Pythonw) {
  $Python = (Get-Command python.exe -ErrorAction Stop).Source
  Start-Process -FilePath $Python -ArgumentList @($Uploader, "run") -WindowStyle Hidden
  exit
}

Start-Process -FilePath $Pythonw -ArgumentList @($Uploader, "run") -WindowStyle Hidden
