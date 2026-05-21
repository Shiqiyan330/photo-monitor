param(
  [Parameter(Position = 0)]
  [ValidateSet("login", "run", "once", "status", "logs", "start-hidden", "install-startup", "test-notification")]
  [string]$Command = "status",

  [string]$Server = "http://121.43.132.227",
  [string]$Username = "admin",
  [string]$Password = "admin",
  [string]$Department = "",
  [string]$Station = "uploads",
  [string]$WatchDir = "C:\Users\QiyanShi\Desktop\photo-monitor\photo-backend\",
  [int]$IntervalSeconds = 60,
  [int]$StableSeconds = 10,
  [int]$TimeoutSeconds = 120,
  [int]$TailLines = 80,
  [switch]$NoSubdirectories,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$Script:StartupParameters = @{} + $PSBoundParameters

$AppName = "PhotoMonitorUploader"
$PhotoExtensions = @(".jpg", ".jpeg", ".png", ".webp")
$KnownPhotoStations = @("xiazhan", "shangzhan")
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
  $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
  try {
    if ((Test-Path -LiteralPath $LogFile) -and (Get-Item -LiteralPath $LogFile).Length -gt $MaxLogBytes) {
      $archive = "$LogFile.$(Get-Date -Format 'yyyyMMddHHmmss').old"
      Move-Item -LiteralPath $LogFile -Destination $archive -Force
    }
    Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
  } catch {
    Write-Host "log write failed: $($_.Exception.Message)"
  }
  if ($Host.Name -ne "Default Host") {
    Write-Host $line
  }
}

function Show-UploaderNotification {
  param([string]$Title, [string]$Message)

  try {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $notify = [System.Windows.Forms.NotifyIcon]::new()
    $notify.Icon = [System.Drawing.SystemIcons]::Information
    $notify.BalloonTipTitle = $Title
    $notify.BalloonTipText = $Message
    $notify.Visible = $true
    $notify.ShowBalloonTip(5000)
    Start-Sleep -Milliseconds 1500
    $notify.Dispose()
    Write-UploaderLog "notification shown: balloon title=$Title"
    return
  } catch {
    $balloonError = $_.Exception.Message
    try {
      [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
      [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

      $escapedTitle = [System.Security.SecurityElement]::Escape($Title)
      $escapedMessage = [System.Security.SecurityElement]::Escape($Message)
      $template = @"
<toast>
  <visual>
    <binding template="ToastGeneric">
      <text>$escapedTitle</text>
      <text>$escapedMessage</text>
    </binding>
  </visual>
</toast>
"@
      $xml = [Windows.Data.Xml.Dom.XmlDocument]::new()
      $xml.LoadXml($template)
      $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
      $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($AppName)
      $notifier.Show($toast)
      Write-UploaderLog "notification requested: toast title=$Title"
    } catch {
      Write-UploaderLog "notification failed: balloon=$balloonError toast=$($_.Exception.Message)"
    }
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

function Assert-LoginConfig {
  param([switch]$Quiet)

  $config = Read-JsonFile $ConfigFile $null
  if (-not $config) {
    $message = "not logged in: please run login first."
    Write-UploaderLog $message
    throw $message
  }

  foreach ($field in @("server", "token", "username", "department", "watch_dir")) {
    if (-not (Get-ConfigValue $config $field "")) {
      $message = "login config invalid: missing $field. Please run login again."
      Write-UploaderLog $message
      throw $message
    }
  }

  if (-not (Test-Path -LiteralPath $config.watch_dir)) {
    $message = "login config invalid: watch directory not found: $($config.watch_dir). Please run login again with -WatchDir."
    Write-UploaderLog $message
    throw $message
  }

  try {
    $headers = @{ Authorization = "Bearer $($config.token)" }
    $serverUrl = Normalize-Server ([string]$config.server)
    $result = Invoke-RestMethod -Uri "$serverUrl/auth/me" -Method Get -Headers $headers -TimeoutSec ([int](Get-ConfigValue $config "timeout_seconds" $TimeoutSeconds))
    if (-not $result.authenticated) {
      throw "server returned unauthenticated response"
    }
    if (-not $Quiet) {
      Write-UploaderLog "login check ok: user=$($config.username) watch_dir=$($config.watch_dir)"
    }
  } catch {
    $message = "login check failed: $($_.Exception.Message). Please run login again."
    Write-UploaderLog $message
    throw $message
  }

  return $config
}

function Update-ConfigFromParameters {
  $config = Read-JsonFile $ConfigFile $null
  if (-not $config) {
    return
  }

  $changed = $false
  if ([string](Get-ConfigValue $config "target" "photo") -ne "photo") {
    $config.target = "photo"
    $changed = $true
  }
  if ($Script:StartupParameters.ContainsKey("WatchDir")) {
    if (-not (Test-Path -LiteralPath $WatchDir)) {
      throw "Watch directory not found: $WatchDir"
    }
    $config.watch_dir = (Resolve-Path -LiteralPath $WatchDir).Path
    $changed = $true
  }
  if ($Script:StartupParameters.ContainsKey("Department")) {
    $config.department = $Department
    $changed = $true
  }
  if ($Script:StartupParameters.ContainsKey("Station")) {
    $config.station = $Station
    $changed = $true
  }
  if ($Script:StartupParameters.ContainsKey("IntervalSeconds")) {
    $config.interval_seconds = $IntervalSeconds
    $changed = $true
  }
  if ($Script:StartupParameters.ContainsKey("StableSeconds")) {
    $config.stable_seconds = $StableSeconds
    $changed = $true
  }
  if ($Script:StartupParameters.ContainsKey("TimeoutSeconds")) {
    $config.timeout_seconds = $TimeoutSeconds
    $changed = $true
  }
  if ($Script:StartupParameters.ContainsKey("NoSubdirectories")) {
    $config.include_subdirectories = (-not $NoSubdirectories.IsPresent)
    $changed = $true
  }

  if ($changed) {
    Save-JsonFile $ConfigFile $config
    Write-UploaderLog "config updated from command line: target=photo watch_dir=$($config.watch_dir)"
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
    target = "photo"
    watch_dir = (Resolve-Path -LiteralPath $WatchDir).Path
    interval_seconds = $IntervalSeconds
    stable_seconds = $StableSeconds
    timeout_seconds = $TimeoutSeconds
    include_subdirectories = (-not $NoSubdirectories.IsPresent)
  }
  Save-JsonFile $ConfigFile $config
  Write-UploaderLog "login ok: user=$($config.username) department=$Department target=photo watch_dir=$($config.watch_dir)"
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

function Resolve-PhotoStation {
  param($Config, [System.IO.FileInfo]$File)

  $configuredStation = [string](Get-ConfigValue $Config "station" "uploads")
  foreach ($part in $File.FullName.Split([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)) {
    if ($KnownPhotoStations -contains $part.ToLowerInvariant()) {
      return $part.ToLowerInvariant()
    }
  }
  return $configuredStation
}

function Get-WatchedFiles {
  param($Config, [string[]]$Extensions)

  $includeSubdirectories = [bool](Get-ConfigValue $Config "include_subdirectories" $true)
  $getChildItemParams = @{
    LiteralPath = [string]$Config.watch_dir
    File = $true
    Force = $true
    ErrorAction = "SilentlyContinue"
  }

  if ($includeSubdirectories) {
    $getChildItemParams.Recurse = $true
  }

  Get-ChildItem @getChildItemParams |
    Where-Object {
      $Extensions -contains $_.Extension.ToLowerInvariant() -and
      $_.Name -notlike "*.tmp" -and
      $_.Name -notlike ".*"
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
    $stationName = Resolve-PhotoStation $Config $File
    $content.Add([System.Net.Http.StringContent]::new($stationName), "station")

    $stream = [System.IO.File]::Open($File.FullName, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
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
  Update-ConfigFromParameters
  $config = Assert-LoginConfig -Quiet

  $state = Read-JsonFile $StateFile ([pscustomobject]@{})
  $stateMap = @{}
  foreach ($property in $state.PSObject.Properties) {
    $stateMap[$property.Name] = $property.Value
  }

  $extensions = $PhotoExtensions
  $uploaded = 0
  $includeSubdirectories = [bool](Get-ConfigValue $config "include_subdirectories" $true)
  Write-UploaderLog "scan starting: include_subdirectories=$includeSubdirectories watch_dir=$($config.watch_dir)"
  $scanStartedAt = Get-Date
  try {
    $files = @(Get-WatchedFiles $config $extensions)
  } catch {
    Write-UploaderLog "scan enumerate failed: watch_dir=$($config.watch_dir) error=$($_.Exception.Message)"
    throw
  }
  $scanElapsedMs = [int](((Get-Date) - $scanStartedAt).TotalMilliseconds)
  Write-UploaderLog "scan started: files=$($files.Count) elapsed_ms=$scanElapsedMs include_subdirectories=$includeSubdirectories watch_dir=$($config.watch_dir)"

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
        target = "photo"
        station = Resolve-PhotoStation $config $file
        uploaded_at = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        server_item = $result.item
      }
      Save-JsonFile $StateFile $stateMap
      $uploaded += 1
      Write-UploaderLog "uploaded: $($file.FullName)"
      Show-UploaderNotification "照片上传成功" "$($file.Name) 已上传到 $($stateMap[$key].station)"
    } catch {
      Write-UploaderLog "upload failed: $($file.FullName) error=$($_.Exception.Message)"
    }
  }

  return $uploaded
}

function Start-RunLoop {
  Update-ConfigFromParameters
  $config = Assert-LoginConfig

  $interval = [int](Get-ConfigValue $config "interval_seconds" $IntervalSeconds)
  if ($IntervalSeconds -gt 0 -and $PSBoundParameters.ContainsKey("IntervalSeconds")) {
    $interval = $IntervalSeconds
  }

  $mutex = [System.Threading.Mutex]::new($false, $MutexName)
  if (-not $mutex.WaitOne(0)) {
    throw "Uploader is already running."
  }

  try {
    Write-UploaderLog "uploader started: interval=${interval}s target=photo watch_dir=$($config.watch_dir)"
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

function Stop-ExistingUploaderProcesses {
  $script = [System.IO.Path]::GetFullPath($PSCommandPath)
  $escapedScript = [regex]::Escape($script)
  $currentPid = $PID
  $stopped = 0

  try {
    $processes = Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe' OR Name = 'pwsh.exe'"
  } catch {
    $processes = Get-WmiObject Win32_Process -Filter "Name = 'powershell.exe' OR Name = 'pwsh.exe'"
  }

  foreach ($process in $processes) {
    if ($process.ProcessId -eq $currentPid -or -not $process.CommandLine) {
      continue
    }

    $commandLine = [string]$process.CommandLine
    $isSameScript = $commandLine -match $escapedScript
    $isRunMode = $commandLine -match '(^|\s|")run("|\s|$)'
    if (-not ($isSameScript -and $isRunMode)) {
      continue
    }

    try {
      Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
      $stopped += 1
      Write-UploaderLog "stopped existing uploader process: pid=$($process.ProcessId)"
    } catch {
      Write-UploaderLog "failed to stop existing uploader process: pid=$($process.ProcessId) error=$($_.Exception.Message)"
    }
  }

  return $stopped
}

function Start-HiddenUploader {
  Update-ConfigFromParameters
  Assert-LoginConfig | Out-Null
  $script = $PSCommandPath
  $stopped = Stop-ExistingUploaderProcesses
  Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$script`"",
    "run"
  ) -WindowStyle Hidden
  Write-UploaderLog "uploader started in background: stopped_previous=$stopped"
  Write-Host "Uploader started in background. Previous uploader processes stopped: $stopped"
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
  Update-ConfigFromParameters
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
  Write-Host "target: photo"
  Write-Host "watch_dir: $($config.watch_dir)"
  Write-Host "interval_seconds: $(Get-ConfigValue $config "interval_seconds" $IntervalSeconds)"
  Write-Host "stable_seconds: $(Get-ConfigValue $config "stable_seconds" $StableSeconds)"
  Write-Host "include_subdirectories: $(Get-ConfigValue $config "include_subdirectories" $true)"
  Write-Host "uploaded records: $count"
}

function Show-Logs {
  Write-Host "log: $LogFile"
  if (-not (Test-Path -LiteralPath $LogFile)) {
    Write-Host "log file does not exist yet."
    return
  }

  Get-Content -LiteralPath $LogFile -Tail $TailLines -Encoding UTF8
}

function Invoke-TestNotification {
  Show-UploaderNotification "照片上传测试" "如果你看到这条通知，说明通知通道可用。"
  Write-Host "Test notification requested. Check Windows notification center."
}

switch ($Command) {
  "login" { Invoke-Login }
  "run" { Start-RunLoop }
  "once" {
    try {
      $count = Invoke-ScanOnce
      Write-Host "uploaded $count file(s)"
    } catch {
      Write-UploaderLog "once failed: $($_.Exception.Message)"
      throw
    }
  }
  "status" { Show-Status }
  "logs" { Show-Logs }
  "start-hidden" { Start-HiddenUploader }
  "install-startup" { Install-Startup }
  "test-notification" { Invoke-TestNotification }
}
