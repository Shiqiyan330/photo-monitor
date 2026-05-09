param(
  [Parameter(Position = 0)]
  [ValidateSet("login", "run", "once", "status", "start-hidden", "install-startup")]
  [string]$Command = "status",

  [string]$Server = "http://121.43.132.227",
  [string]$Username = "admin",
  [string]$Password = "",
  [string]$Department = "",
  [string]$Station = "uploads",
  [ValidateSet("photo", "files", "ledgers")]
  [string]$Target = "photo",
  [string]$WatchDir = "C:\Users\QiyanShi\Desktop\photo-monitor\photo-backend\photos\photos\photos",
  [int]$IntervalSeconds = 60,
  [int]$StableSeconds = 10,
  [int]$TimeoutSeconds = 120,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$AppName = "PhotoMonitorUploader"
$AllowedExtensions = @(".jpg", ".jpeg", ".png", ".webp", ".zip", ".csv", ".xlsx", ".xls", ".json", ".txt", ".pdf")
$LedgerExtensions = @(".csv", ".xlsx", ".xls", ".json", ".txt", ".pdf", ".zip")
$MaxUploadBytes = 200MB
$MaxLogBytes = 5MB
$MutexName = "Global\PhotoMonitorUploader"

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
  if ((Test-Path -LiteralPath $LogFile) -and (Get-Item -LiteralPath $LogFile).Length -gt $MaxLogBytes) {
    $archive = "$LogFile.$(Get-Date -Format 'yyyyMMddHHmmss').old"
    Move-Item -LiteralPath $LogFile -Destination $archive -Force
  }

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
  $temp = "$Path.tmp"
  Set-Content -LiteralPath $temp -Value $json -Encoding UTF8
  Move-Item -LiteralPath $temp -Destination $Path -Force
}

function Normalize-Server {
  param([string]$Value)
  return $Value.TrimEnd("/")
}

function Get-ConfigValue {
  param($Config, [string]$Name, $DefaultValue)
  $property = $Config.PSObject.Properties[$Name]
  if ($property -and $null -ne $property.Value -and "$($property.Value)" -ne "") {
    return $property.Value
  }
  return $DefaultValue
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
  if (-not (Test-Path -LiteralPath $WatchDir)) {
    throw "Watch directory not found: $WatchDir"
  }

  $serverUrl = Normalize-Server $Server
  $payload = @{ username = $Username; password = $Password } | ConvertTo-Json
  $result = Invoke-RestMethod -Uri "$serverUrl/auth/login" -Method Post -ContentType "application/json" -Body $payload -TimeoutSec $TimeoutSeconds

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
    target = $Target
    watch_dir = (Resolve-Path -LiteralPath $WatchDir).Path
    interval_seconds = $IntervalSeconds
    stable_seconds = $StableSeconds
    timeout_seconds = $TimeoutSeconds
  }
  Save-JsonFile $ConfigFile $config
  Write-UploaderLog "login ok: user=$($config.username) department=$Department target=$Target watch_dir=$($config.watch_dir)"
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

function Get-UploadPath {
  param([string]$TargetName)
  switch ($TargetName) {
    "files" { return "/uploads/files" }
    "ledgers" { return "/uploads/ledgers" }
    default { return "/uploads" }
  }
}

function Invoke-UploadFile {
  param($Config, [System.IO.FileInfo]$File)

  Add-Type -AssemblyName System.Net.Http
  $client = [System.Net.Http.HttpClient]::new()
  $content = [System.Net.Http.MultipartFormDataContent]::new()
  $stream = $null
  try {
    $client.Timeout = [TimeSpan]::FromSeconds([Math]::Max(10, [int](Get-ConfigValue $Config "timeout_seconds" $TimeoutSeconds)))
    $client.DefaultRequestHeaders.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new("Bearer", [string]$Config.token)
    $content.Add([System.Net.Http.StringContent]::new([string]$Config.department), "department")
    $content.Add([System.Net.Http.StringContent]::new([string](Get-ConfigValue $Config "station" "uploads")), "station")

    $stream = [System.IO.File]::Open($File.FullName, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    $fileContent = [System.Net.Http.StreamContent]::new($stream)
    $content.Add($fileContent, "file", $File.Name)

    $targetName = [string](Get-ConfigValue $Config "target" "photo")
    $uploadPath = Get-UploadPath $targetName
    $response = $client.PostAsync("$($Config.server)$uploadPath", $content).Result
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

  $targetName = [string](Get-ConfigValue $config "target" "photo")
  $extensions = if ($targetName -eq "ledgers") { $LedgerExtensions } else { $AllowedExtensions }
  $uploaded = 0
  $files = Get-ChildItem -LiteralPath $config.watch_dir -Recurse -File |
    Where-Object { $extensions -contains $_.Extension.ToLowerInvariant() -and $_.Name -notlike "*.tmp" }

  foreach ($file in $files) {
    try {
      $key = Get-FileKey $file
      if ($stateMap.ContainsKey($key)) {
        continue
      }
      if (-not (Test-StableFile $file ([int](Get-ConfigValue $config "stable_seconds" $StableSeconds)))) {
        continue
      }
      if ($file.Length -gt $MaxUploadBytes) {
        Write-UploaderLog "skip too large: $($file.FullName)"
        continue
      }

      if ($DryRun) {
        Write-UploaderLog "dry-run matched: $($file.FullName)"
        continue
      }

      $result = Invoke-UploadFile $config $file
      $stateMap[$key] = [ordered]@{
        path = $file.FullName
        target = $targetName
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

  $interval = [int](Get-ConfigValue $config "interval_seconds" $IntervalSeconds)
  if ($IntervalSeconds -gt 0 -and $PSBoundParameters.ContainsKey("IntervalSeconds")) {
    $interval = $IntervalSeconds
  }

  $mutex = [System.Threading.Mutex]::new($false, $MutexName)
  if (-not $mutex.WaitOne(0)) {
    throw "Uploader is already running."
  }

  try {
    Write-UploaderLog "uploader started: interval=${interval}s target=$(Get-ConfigValue $config "target" "photo") watch_dir=$($config.watch_dir)"
    while ($true) {
      $count = Invoke-ScanOnce
      if ($count -gt 0) {
        Write-UploaderLog "scan complete: uploaded=$count"
      }
      Start-Sleep -Seconds $interval
    }
  } finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
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
  if (-not $config) {
    Write-Host "status: not logged in"
    return
  }
  Write-Host "server: $($config.server)"
  Write-Host "user: $($config.username)"
  Write-Host "department: $($config.department)"
  Write-Host "target: $(Get-ConfigValue $config "target" "photo")"
  Write-Host "watch_dir: $($config.watch_dir)"
  Write-Host "interval_seconds: $(Get-ConfigValue $config "interval_seconds" $IntervalSeconds)"
  Write-Host "stable_seconds: $(Get-ConfigValue $config "stable_seconds" $StableSeconds)"
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
