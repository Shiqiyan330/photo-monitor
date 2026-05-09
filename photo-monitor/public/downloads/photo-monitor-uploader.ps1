param(
  [Parameter(Position = 0)]
  [ValidateSet("login", "run", "once", "status", "start-hidden", "install-startup")]
  [string]$Command = "status",

  [string]$Server = "http://127.0.0.1:8000",
  [string]$Username = "",
  [string]$Password = "",
  [string]$Department = "",
  [string]$Station = "uploads",
  [string]$WatchDir = "",
  [int]$IntervalSeconds = 60,
  [int]$StableSeconds = 10
)

$ErrorActionPreference = "Stop"

$AppName = "PhotoMonitorUploader"
$AllowedExtensions = @(".jpg", ".jpeg", ".png", ".webp", ".zip", ".csv", ".xlsx", ".xls", ".json", ".txt", ".pdf")
$MaxUploadBytes = 50MB

function Get-AppDir {
  $candidates = @()
  if ($env:PHOTOMONITOR_UPLOADER_HOME) {
    $candidates += $env:PHOTOMONITOR_UPLOADER_HOME
  }
  if ($env:LOCALAPPDATA) {
    $candidates += (Join-Path $env:LOCALAPPDATA $AppName)
  }
  if ($PSCommandPath) {
    $candidates += (Join-Path (Split-Path -Parent $PSCommandPath) ".photo-monitor-uploader")
  }
  $candidates += (Join-Path $PWD ".photo-monitor-uploader")

  foreach ($dir in $candidates) {
    try {
      New-Item -ItemType Directory -Path $dir -Force -ErrorAction Stop | Out-Null
      return $dir
    } catch {
      continue
    }
  }

  throw "Cannot create uploader config directory."
}

$AppDir = Get-AppDir
$ConfigFile = Join-Path $AppDir "config.json"
$StateFile = Join-Path $AppDir "uploaded_state.json"
$LogFile = Join-Path $AppDir "uploader.log"

function Write-UploaderLog {
  param([string]$Message)
  $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
  Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
  if ($Host.Name -ne "Default Host") {
    Write-Host $line
  }
}

function Read-JsonFile {
  param($Path, $DefaultValue)
  if (-not (Test-Path -LiteralPath $Path)) {
    return $DefaultValue
  }
  return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Save-JsonFile {
  param($Path, $Value)
  $json = $Value | ConvertTo-Json -Depth 10
  Set-Content -LiteralPath $Path -Value $json -Encoding UTF8
}

function Normalize-Server {
  param([string]$Value)
  return $Value.TrimEnd("/")
}

function Get-PlainPassword {
  param([string]$Prompt)
  $secure = Read-Host $Prompt -AsSecureString
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try {
    return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
  }
}

function Invoke-Login {
  if (-not $Username) {
    $Username = Read-Host "Username"
  }
  if (-not $Password) {
    $Password = Get-PlainPassword "Password"
  }
  if (-not $WatchDir) {
    $WatchDir = Read-Host "Watch directory"
  }

  $serverUrl = Normalize-Server $Server
  $payload = @{ username = $Username; password = $Password } | ConvertTo-Json
  $result = Invoke-RestMethod -Uri "$serverUrl/auth/login" -Method Post -ContentType "application/json" -Body $payload

  if (-not $Department) {
    $Department = $result.user.department
  }
  if (-not $Department) {
    $Department = Read-Host "Upload department"
  }
  if (-not $Department) {
    throw "Department is required."
  }

  $config = [ordered]@{
    server = $serverUrl
    token = $result.token
    username = $result.user.username
    department = $Department
    station = $Station
    watch_dir = (Resolve-Path -LiteralPath $WatchDir).Path
    interval_seconds = $IntervalSeconds
    stable_seconds = $StableSeconds
  }
  Save-JsonFile $ConfigFile $config
  Write-UploaderLog "login ok: user=$($config.username) department=$Department watch_dir=$($config.watch_dir)"
  Write-Host "Login success. Config saved to $ConfigFile"
}

function Get-FileKey {
  param([System.IO.FileInfo]$File)
  return "$($File.FullName)|$($File.Length)|$([int64]($File.LastWriteTimeUtc - [datetime]'1970-01-01').TotalSeconds)"
}

function Test-StableFile {
  param([System.IO.FileInfo]$File, [int]$Seconds)
  $age = ((Get-Date) - $File.LastWriteTime).TotalSeconds
  return $File.Length -gt 0 -and $age -ge $Seconds
}

function Invoke-UploadFile {
  param($Config, [System.IO.FileInfo]$File)

  Add-Type -AssemblyName System.Net.Http
  $client = [System.Net.Http.HttpClient]::new()
  $content = [System.Net.Http.MultipartFormDataContent]::new()
  try {
    $client.DefaultRequestHeaders.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new("Bearer", [string]$Config.token)
    $content.Add([System.Net.Http.StringContent]::new([string]$Config.department), "department")
    $content.Add([System.Net.Http.StringContent]::new([string]$Config.station), "station")

    $stream = [System.IO.File]::OpenRead($File.FullName)
    $fileContent = [System.Net.Http.StreamContent]::new($stream)
    $content.Add($fileContent, "file", $File.Name)

    $response = $client.PostAsync("$($Config.server)/uploads", $content).Result
    $text = $response.Content.ReadAsStringAsync().Result
    if (-not $response.IsSuccessStatusCode) {
      throw "HTTP $([int]$response.StatusCode): $text"
    }
    return $text | ConvertFrom-Json
  } finally {
    if ($stream) { $stream.Dispose() }
    $content.Dispose()
    $client.Dispose()
  }
}

function Invoke-ScanOnce {
  $config = Read-JsonFile $ConfigFile $null
  if (-not $config) {
    throw "Please run login first."
  }
  if (-not (Test-Path -LiteralPath $config.watch_dir)) {
    Write-UploaderLog "watch directory not found: $($config.watch_dir)"
    return 0
  }

  $state = Read-JsonFile $StateFile ([pscustomobject]@{})
  $stateMap = @{}
  foreach ($property in $state.PSObject.Properties) {
    $stateMap[$property.Name] = $property.Value
  }

  $uploaded = 0
  $files = Get-ChildItem -LiteralPath $config.watch_dir -Recurse -File |
    Where-Object { $AllowedExtensions -contains $_.Extension.ToLowerInvariant() }

  foreach ($file in $files) {
    try {
      $key = Get-FileKey $file
      if ($stateMap.ContainsKey($key)) {
        continue
      }
      if (-not (Test-StableFile $file ([int]$config.stable_seconds))) {
        continue
      }
      if ($file.Length -gt $MaxUploadBytes) {
        Write-UploaderLog "skip too large: $($file.FullName)"
        continue
      }

      $result = Invoke-UploadFile $config $file
      $stateMap[$key] = [ordered]@{
        path = $file.FullName
        uploaded_at = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        server_item = $result.item
      }
      Save-JsonFile $StateFile $stateMap
      $uploaded += 1
      Write-UploaderLog "uploaded: $($file.FullName)"
    } catch {
      Write-UploaderLog "upload failed: $($file.FullName) error=$($_.Exception.Message)"
    }
  }

  return $uploaded
}

function Start-RunLoop {
  $config = Read-JsonFile $ConfigFile $null
  if (-not $config) {
    throw "Please run login first."
  }

  $interval = [int]$config.interval_seconds
  if ($IntervalSeconds -gt 0 -and $PSBoundParameters.ContainsKey("IntervalSeconds")) {
    $interval = $IntervalSeconds
  }

  Write-UploaderLog "uploader started: interval=${interval}s watch_dir=$($config.watch_dir)"
  while ($true) {
    $count = Invoke-ScanOnce
    if ($count -gt 0) {
      Write-UploaderLog "scan complete: uploaded=$count"
    }
    Start-Sleep -Seconds $interval
  }
}

function Start-HiddenUploader {
  $script = $PSCommandPath
  Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$script`"",
    "run"
  ) -WindowStyle Hidden
  Write-Host "Uploader started in background."
}

function Install-Startup {
  $startup = [Environment]::GetFolderPath("Startup")
  $shortcutPath = Join-Path $startup "PhotoMonitorUploader.lnk"
  $shell = New-Object -ComObject WScript.Shell
  $shortcut = $shell.CreateShortcut($shortcutPath)
  $shortcut.TargetPath = "powershell.exe"
  $shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSCommandPath`" run"
  $shortcut.WorkingDirectory = Split-Path -Parent $PSCommandPath
  $shortcut.Save()
  Write-Host "Startup shortcut created: $shortcutPath"
}

function Show-Status {
  $config = Read-JsonFile $ConfigFile $null
  $state = Read-JsonFile $StateFile ([pscustomobject]@{})
  $count = @($state.PSObject.Properties).Count
  Write-Host "config: $ConfigFile"
  Write-Host "log: $LogFile"
  Write-Host "server: $($config.server)"
  Write-Host "user: $($config.username)"
  Write-Host "department: $($config.department)"
  Write-Host "watch_dir: $($config.watch_dir)"
  Write-Host "uploaded records: $count"
}

switch ($Command) {
  "login" { Invoke-Login }
  "run" { Start-RunLoop }
  "once" { $count = Invoke-ScanOnce; Write-Host "uploaded $count file(s)" }
  "status" { Show-Status }
  "start-hidden" { Start-HiddenUploader }
  "install-startup" { Install-Startup }
}
