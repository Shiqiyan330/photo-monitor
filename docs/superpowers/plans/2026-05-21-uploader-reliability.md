# Uploader Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `scripts/photo-monitor-uploader.ps1` safer for unattended Windows uploads and easier to diagnose when it fails.

**Architecture:** Keep the uploader as a single PowerShell script because the project already distributes one script and the current command model is simple. Add small helper functions inside the script for validation, retry, diagnostics, and process inspection, then update the README so operators can use the new behavior without reading code.

**Tech Stack:** Windows PowerShell 5.1-compatible PowerShell, .NET `System.Net.Http.HttpClient`, local JSON config/state files, Git.

---

## File Structure

- Modify: `scripts/photo-monitor-uploader.ps1`
  - Owns command parsing, config/state persistence, scanning, uploading, notifications, hidden startup, logs, and diagnostics.
  - Add reliability helpers in the existing helper area near `Read-JsonFile`, `Save-JsonFile`, and `Normalize-Server`.
  - Add `doctor` as a new command and function near `Show-Status`/`Show-Logs`.
- Modify: `scripts/README-local-uploader.md`
  - Replace the mojibake text with readable Chinese usage docs.
  - Document `doctor`, retry parameters, and verification commands.

No backend files change. No frontend files change.

---

### Task 1: Script Reliability Helpers

**Files:**
- Modify: `scripts/photo-monitor-uploader.ps1`
- Test: PowerShell parser and `status`

- [ ] **Step 1: Add numeric parameters and command entry**

In `scripts/photo-monitor-uploader.ps1`, update the `param` block so it includes `doctor`, parameter ranges, and retry settings:

```powershell
[ValidateSet("login", "run", "once", "status", "logs", "start-hidden", "install-startup", "test-notification", "doctor")]
[string]$Command = "status",

[string]$Server = "http://121.43.132.227",
[string]$Username = "admin",
[string]$Password = "admin",
[string]$Department = "",
[string]$Station = "uploads",
[string]$WatchDir = "C:\Users\QiyanShi\Desktop\photo-monitor\photo-backend\",
[ValidateRange(5, 86400)]
[int]$IntervalSeconds = 60,
[ValidateRange(0, 3600)]
[int]$StableSeconds = 10,
[ValidateRange(10, 3600)]
[int]$TimeoutSeconds = 120,
[ValidateRange(1, 1000)]
[int]$TailLines = 80,
[ValidateRange(1, 10)]
[int]$RetryCount = 3,
[ValidateRange(1, 300)]
[int]$RetryDelaySeconds = 5,
[switch]$NoSubdirectories,
[switch]$DryRun
```

- [ ] **Step 2: Run parser and verify expected failure or pass**

Run:

```powershell
$tokens=$null;$errors=$null; [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path scripts\photo-monitor-uploader.ps1), [ref]$tokens, [ref]$errors) | Out-Null; $errors
```

Expected: no parser errors.

- [ ] **Step 3: Add validation and JSON helper code**

Add or update these helpers below `Write-UploaderLog` and around existing JSON helpers:

```powershell
$SafePathPartPattern = '^[^<>:"/\\|?*\x00-\x1f]+$'

function Format-ExceptionMessage {
  param($ErrorRecord)

  $exception = $ErrorRecord.Exception
  if ($exception.InnerException) {
    return "$($exception.Message) inner=$($exception.InnerException.Message)"
  }
  return $exception.Message
}

function Read-JsonFile {
  param($Path, $DefaultValue)
  if (-not (Test-Path -LiteralPath $Path)) {
    return $DefaultValue
  }
  try {
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
  } catch {
    Write-UploaderLog "json read failed: path=$Path error=$(Format-ExceptionMessage $_)"
    return $DefaultValue
  }
}

function Save-JsonFile {
  param($Path, $Value)
  $dir = Split-Path -Parent $Path
  if ($dir) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
  }
  $json = $Value | ConvertTo-Json -Depth 10
  $temp = "$Path.tmp"
  Set-Content -LiteralPath $temp -Value $json -Encoding UTF8
  Move-Item -LiteralPath $temp -Destination $Path -Force
}

function Normalize-Server {
  param([string]$Value)
  $trimmed = $Value.Trim().TrimEnd("/")
  if (-not $trimmed) {
    throw "Server is required."
  }
  try {
    $uri = [Uri]$trimmed
  } catch {
    throw "Server is not a valid URI: $Value"
  }
  if ($uri.Scheme -notin @("http", "https")) {
    throw "Server must start with http:// or https://"
  }
  return $trimmed
}

function Assert-SafePathPart {
  param([string]$Name, [string]$Value)

  $normalized = $Value.Trim()
  if (-not $normalized) {
    throw "$Name is required."
  }
  if ($normalized -notmatch $SafePathPartPattern -or $normalized -in @(".", "..")) {
    throw "$Name contains invalid path characters: $Value"
  }
  return $normalized
}
```

- [ ] **Step 4: Wire validation into config updates and login**

In `Update-ConfigFromParameters`, make department and station assignments call `Assert-SafePathPart`. In `Invoke-Login`, validate `$Department` and `$Station` before writing config:

```powershell
if ($Script:StartupParameters.ContainsKey("Department")) {
  $config.department = Assert-SafePathPart "Department" $Department
  $changed = $true
}
if ($Script:StartupParameters.ContainsKey("Station")) {
  $config.station = Assert-SafePathPart "Station" $Station
  $changed = $true
}
if ($Script:StartupParameters.ContainsKey("RetryCount")) {
  $config.retry_count = $RetryCount
  $changed = $true
}
if ($Script:StartupParameters.ContainsKey("RetryDelaySeconds")) {
  $config.retry_delay_seconds = $RetryDelaySeconds
  $changed = $true
}
```

In `Invoke-Login`, add:

```powershell
$Department = Assert-SafePathPart "Department" $Department
$Station = Assert-SafePathPart "Station" $Station
```

Also save:

```powershell
retry_count = $RetryCount
retry_delay_seconds = $RetryDelaySeconds
```

- [ ] **Step 5: Run parser and status**

Run:

```powershell
$tokens=$null;$errors=$null; [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path scripts\photo-monitor-uploader.ps1), [ref]$tokens, [ref]$errors) | Out-Null; $errors
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 status
```

Expected: parser output is empty, `status` prints config/log paths and current settings.

- [ ] **Step 6: Commit Task 1**

```powershell
git add scripts/photo-monitor-uploader.ps1
git commit -m "feat: harden uploader config handling"
```

---

### Task 2: Upload Retry and Hidden Startup Preservation

**Files:**
- Modify: `scripts/photo-monitor-uploader.ps1`
- Test: parser, `status`, and `once -DryRun`

- [ ] **Step 1: Improve upload error parsing**

In `Invoke-UploadFile`, replace `.Result` calls with `.GetAwaiter().GetResult()` and extract JSON `detail` on non-success responses:

```powershell
$response = $client.PostAsync("$($Config.server)/uploads", $content).GetAwaiter().GetResult()
$text = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
if (-not $response.IsSuccessStatusCode) {
  $detail = $text
  try {
    $errorPayload = $text | ConvertFrom-Json
    if ($errorPayload.detail) {
      $detail = $errorPayload.detail
    }
  } catch {
    $detail = $text
  }
  throw "HTTP $([int]$response.StatusCode): $detail"
}
return $text | ConvertFrom-Json
```

- [ ] **Step 2: Add retry wrapper**

Add this function after `Invoke-UploadFile`:

```powershell
function Invoke-UploadFileWithRetry {
  param($Config, [System.IO.FileInfo]$File)

  $attempts = [Math]::Max(1, [int](Get-ConfigValue $Config "retry_count" $RetryCount))
  $delaySeconds = [Math]::Max(1, [int](Get-ConfigValue $Config "retry_delay_seconds" $RetryDelaySeconds))

  for ($attempt = 1; $attempt -le $attempts; $attempt += 1) {
    try {
      if ($attempt -gt 1) {
        Write-UploaderLog "upload retrying: attempt=$attempt/$attempts file=$($File.FullName)"
      }
      return Invoke-UploadFile $Config $File
    } catch {
      if ($attempt -ge $attempts) {
        throw
      }
      Write-UploaderLog "upload attempt failed: attempt=$attempt/$attempts file=$($File.FullName) error=$(Format-ExceptionMessage $_)"
      Start-Sleep -Seconds $delaySeconds
    }
  }
}
```

In `Invoke-ScanOnce`, replace:

```powershell
$result = Invoke-UploadFile $config $file
```

with:

```powershell
$result = Invoke-UploadFileWithRetry $config $file
```

- [ ] **Step 3: Preserve effective config for hidden startup**

In `Start-HiddenUploader`, keep the validated config returned by `Assert-LoginConfig` and pass effective values to the hidden process:

```powershell
$config = Assert-LoginConfig
$script = $PSCommandPath
$stopped = Stop-ExistingUploaderProcesses
$runIntervalSeconds = [int](Get-ConfigValue $config "interval_seconds" $IntervalSeconds)
$runStableSeconds = [int](Get-ConfigValue $config "stable_seconds" $StableSeconds)
$runTimeoutSeconds = [int](Get-ConfigValue $config "timeout_seconds" $TimeoutSeconds)
$runRetryCount = [int](Get-ConfigValue $config "retry_count" $RetryCount)
$runRetryDelaySeconds = [int](Get-ConfigValue $config "retry_delay_seconds" $RetryDelaySeconds)
Start-Process -FilePath "powershell.exe" -ArgumentList @(
  "-NoProfile",
  "-ExecutionPolicy", "Bypass",
  "-File", "`"$script`"",
  "run",
  "-IntervalSeconds", "$runIntervalSeconds",
  "-StableSeconds", "$runStableSeconds",
  "-TimeoutSeconds", "$runTimeoutSeconds",
  "-RetryCount", "$runRetryCount",
  "-RetryDelaySeconds", "$runRetryDelaySeconds"
) -WindowStyle Hidden
```

- [ ] **Step 4: Expose retry values in status**

In `Show-Status`, add:

```powershell
Write-Host "timeout_seconds: $(Get-ConfigValue $config "timeout_seconds" $TimeoutSeconds)"
Write-Host "retry_count: $(Get-ConfigValue $config "retry_count" $RetryCount)"
Write-Host "retry_delay_seconds: $(Get-ConfigValue $config "retry_delay_seconds" $RetryDelaySeconds)"
```

- [ ] **Step 5: Verify without real upload**

Run:

```powershell
$tokens=$null;$errors=$null; [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path scripts\photo-monitor-uploader.ps1), [ref]$tokens, [ref]$errors) | Out-Null; $errors
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 once -DryRun
```

Expected: parser output is empty; status includes retry fields; dry run scans matching files and prints `uploaded 0 file(s)`.

- [ ] **Step 6: Commit Task 2**

```powershell
git add scripts/photo-monitor-uploader.ps1
git commit -m "feat: add uploader retry handling"
```

---

### Task 3: Doctor Diagnostic Command

**Files:**
- Modify: `scripts/photo-monitor-uploader.ps1`
- Test: `doctor`

- [ ] **Step 1: Add process discovery helper**

Add this helper near `Stop-ExistingUploaderProcesses`:

```powershell
function Get-UploaderRunProcesses {
  $script = [System.IO.Path]::GetFullPath($PSCommandPath)
  $escapedScript = [regex]::Escape($script)
  $currentPid = $PID

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
    if ($commandLine -match $escapedScript -and $commandLine -match '(^|\s|")run("|\s|$)') {
      $process
    }
  }
}
```

Then update `Stop-ExistingUploaderProcesses` to loop over `Get-UploaderRunProcesses` instead of duplicating process discovery.

- [ ] **Step 2: Add doctor output helpers**

Add these helpers near `Show-Status`:

```powershell
function Write-DoctorLine {
  param(
    [ValidateSet("ok", "warn", "fail")]
    [string]$Level,
    [string]$Message
  )

  Write-Host "$Level  $Message"
}

function Get-RecentProblemLogLines {
  if (-not (Test-Path -LiteralPath $LogFile)) {
    return @()
  }
  @(Get-Content -LiteralPath $LogFile -Tail 80 -Encoding UTF8 | Where-Object {
    $_ -match "failed|error|timeout|denied|invalid|not found"
  } | Select-Object -Last 8)
}
```

- [ ] **Step 3: Add `Invoke-Doctor`**

Add this function near `Show-Logs`:

```powershell
function Invoke-Doctor {
  Write-Host "Photo Monitor Uploader doctor"
  Write-Host "config: $ConfigFile"
  Write-Host "log: $LogFile"

  $config = Read-JsonFile $ConfigFile $null
  if (-not $config) {
    Write-DoctorLine "fail" "not logged in; run login first"
  } else {
    Write-DoctorLine "ok" "config file exists"
    foreach ($field in @("server", "token", "username", "department", "watch_dir")) {
      if (Get-ConfigValue $config $field "") {
        Write-DoctorLine "ok" "config field present: $field"
      } else {
        Write-DoctorLine "fail" "config field missing: $field"
      }
    }

    try {
      $serverUrl = Normalize-Server ([string]$config.server)
      Write-DoctorLine "ok" "server url valid: $serverUrl"
    } catch {
      Write-DoctorLine "fail" "server url invalid: $(Format-ExceptionMessage $_)"
    }

    if (Get-ConfigValue $config "watch_dir" "") {
      if (Test-Path -LiteralPath $config.watch_dir) {
        Write-DoctorLine "ok" "watch directory exists: $($config.watch_dir)"
      } else {
        Write-DoctorLine "fail" "watch directory missing: $($config.watch_dir)"
      }
    }

    if (Get-ConfigValue $config "token" "") {
      try {
        $headers = @{ Authorization = "Bearer $($config.token)" }
        $serverUrl = Normalize-Server ([string]$config.server)
        $result = Invoke-RestMethod -Uri "$serverUrl/auth/me" -Method Get -Headers $headers -TimeoutSec ([int](Get-ConfigValue $config "timeout_seconds" $TimeoutSeconds))
        if ($result.authenticated) {
          Write-DoctorLine "ok" "login token accepted: user=$($config.username)"
        } else {
          Write-DoctorLine "fail" "server returned unauthenticated response"
        }
      } catch {
        Write-DoctorLine "fail" "login check failed: $(Format-ExceptionMessage $_)"
      }
    }

    Write-DoctorLine "ok" "interval_seconds=$(Get-ConfigValue $config "interval_seconds" $IntervalSeconds)"
    Write-DoctorLine "ok" "stable_seconds=$(Get-ConfigValue $config "stable_seconds" $StableSeconds)"
    Write-DoctorLine "ok" "timeout_seconds=$(Get-ConfigValue $config "timeout_seconds" $TimeoutSeconds)"
    Write-DoctorLine "ok" "retry_count=$(Get-ConfigValue $config "retry_count" $RetryCount)"
    Write-DoctorLine "ok" "retry_delay_seconds=$(Get-ConfigValue $config "retry_delay_seconds" $RetryDelaySeconds)"
    Write-DoctorLine "ok" "include_subdirectories=$(Get-ConfigValue $config "include_subdirectories" $true)"
  }

  if (Test-Path -LiteralPath $LogFile) {
    Write-DoctorLine "ok" "log file exists"
  } else {
    Write-DoctorLine "warn" "log file does not exist yet"
  }

  $runProcesses = @(Get-UploaderRunProcesses)
  if ($runProcesses.Count -gt 0) {
    Write-DoctorLine "ok" "background uploader process count=$($runProcesses.Count)"
    foreach ($process in $runProcesses) {
      Write-Host "     pid=$($process.ProcessId)"
    }
  } else {
    Write-DoctorLine "warn" "no background run process detected"
  }

  $problemLines = @(Get-RecentProblemLogLines)
  if ($problemLines.Count -gt 0) {
    Write-DoctorLine "warn" "recent problem log lines:"
    foreach ($line in $problemLines) {
      Write-Host "     $line"
    }
  } else {
    Write-DoctorLine "ok" "no recent problem log lines found"
  }
}
```

- [ ] **Step 4: Wire `doctor` into command switch**

In the bottom `switch ($Command)`, add:

```powershell
"doctor" { Invoke-Doctor }
```

- [ ] **Step 5: Verify doctor**

Run:

```powershell
$tokens=$null;$errors=$null; [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path scripts\photo-monitor-uploader.ps1), [ref]$tokens, [ref]$errors) | Out-Null; $errors
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 doctor
```

Expected: parser output is empty; `doctor` prints config/log paths and at least one `ok`, `warn`, or `fail` line.

- [ ] **Step 6: Commit Task 3**

```powershell
git add scripts/photo-monitor-uploader.ps1
git commit -m "feat: add uploader doctor command"
```

---

### Task 4: Documentation and Final Verification

**Files:**
- Modify: `scripts/README-local-uploader.md`
- Test: final command suite

- [ ] **Step 1: Replace README with readable Chinese docs**

Replace `scripts/README-local-uploader.md` with this content:

```markdown
# 照片自动上传脚本使用教程

本文说明如何使用 `scripts\photo-monitor-uploader.ps1` 在 Windows 上监控本地目录，并自动把新增照片上传到服务器。

## 功能

- 登录服务器并保存本地配置
- 持续扫描指定目录
- 默认递归扫描子目录
- 自动上传 `.jpg`、`.jpeg`、`.png`、`.webp`
- 根据路径中的 `xiazhan` / `shangzhan` 自动识别站点
- 上传成功后发送 Windows 通知
- 通过本地状态文件避免重复上传
- 支持隐藏后台运行和开机自启
- 支持 `doctor` 诊断当前运行环境

## 首次登录

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 login -WatchDir C:\Path\To\PhotoFolder
```

显式指定账号、密码、部门：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 login -Server http://121.43.132.227 -Username <用户名> -Password <密码> -Department <部门名称> -WatchDir C:\Path\To\PhotoFolder
```

## 查看状态

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 status
```

## 诊断问题

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 doctor
```

`doctor` 会检查配置、登录态、监控目录、日志文件、后台进程和最近错误日志。

## 扫描一次

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 once
```

只测试匹配文件，不真实上传：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 once -DryRun
```

## 后台隐藏运行

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 start-hidden -WatchDir C:\Path\To\PhotoFolder
```

`start-hidden` 会先检查登录配置，停止旧的上传进程，然后以隐藏窗口启动新的 `run` 进程。

## 开机自启

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 install-startup
```

## 查看日志

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 logs
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 logs -TailLines 120
```

## 测试通知

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 test-notification
```

## 常用参数

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `-Server` | 后端服务器地址 | `http://121.43.132.227` |
| `-Username` | 登录用户名 | `admin` |
| `-Password` | 登录密码 | `admin` |
| `-Department` | 上传部门 | 登录用户部门或手动输入 |
| `-Station` | 路径中没有站点名时使用的默认站点 | `uploads` |
| `-WatchDir` | 本地监控目录 | 脚本默认目录 |
| `-IntervalSeconds` | 持续扫描间隔 | `60` |
| `-StableSeconds` | 文件稳定等待时间 | `10` |
| `-TimeoutSeconds` | 请求超时时间 | `120` |
| `-RetryCount` | 上传失败重试次数 | `3` |
| `-RetryDelaySeconds` | 每次重试前等待秒数 | `5` |
| `-TailLines` | `logs` 显示行数 | `80` |
| `-NoSubdirectories` | 不扫描子目录 | 默认扫描子目录 |
| `-DryRun` | 只检测，不上传 | 默认关闭 |

## 本地文件位置

默认目录：

```text
%LOCALAPPDATA%\PhotoMonitorUploader
```

| 文件 | 说明 |
| --- | --- |
| `config.json` | 登录配置、token、监控目录 |
| `uploaded_state.json` | 已上传文件状态 |
| `uploader.log` | 运行日志 |

## 重置上传状态

```powershell
Remove-Item "$env:LOCALAPPDATA\PhotoMonitorUploader\uploaded_state.json" -Force
```

删除后，下次扫描可能会重新上传当前目录中的文件。

## 常见问题

### 修改脚本默认目录后，后台仍监控旧目录

脚本优先读取 `%LOCALAPPDATA%\PhotoMonitorUploader\config.json`。重新运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 login -WatchDir C:\Path\To\PhotoFolder
```

或：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 start-hidden -WatchDir C:\Path\To\PhotoFolder
```

### 登录失效

重新执行 `login`。

### 目录不存在

先确认目录存在，再运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 status -WatchDir C:\Path\To\PhotoFolder
```

### 没有通知

先运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 test-notification
```

如果仍不显示，检查 Windows 通知设置、勿扰模式或专注助手。

### 上传失败 413

413 表示请求体太大。脚本会跳过超过 `200MB` 的文件；如果小于该限制仍出现 413，需要检查服务器 nginx 或后端上传限制。
```

- [ ] **Step 2: Run final verification suite**

Run:

```powershell
$tokens=$null;$errors=$null; [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path scripts\photo-monitor-uploader.ps1), [ref]$tokens, [ref]$errors) | Out-Null; $errors
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 logs -TailLines 3
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 doctor
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 once -DryRun
```

Expected:

- Parser output is empty.
- `status` exits successfully.
- `logs` exits successfully.
- `doctor` exits successfully and prints diagnostic lines.
- `once -DryRun` exits successfully without uploading files.

- [ ] **Step 3: Inspect final diff**

Run:

```powershell
git diff -- scripts/photo-monitor-uploader.ps1 scripts/README-local-uploader.md
```

Expected: diff only includes the uploader script reliability/diagnostic changes and README documentation changes.

- [ ] **Step 4: Commit Task 4**

```powershell
git add scripts/photo-monitor-uploader.ps1 scripts/README-local-uploader.md
git commit -m "docs: update uploader operations guide"
```

---

## Self-Review Checklist

- Spec coverage:
  - Validation: Task 1.
  - Retry and HTTP error parsing: Task 2.
  - JSON tolerance: Task 1.
  - Hidden startup config preservation: Task 2.
  - Doctor command: Task 3.
  - Documentation refresh: Task 4.
  - Verification without real upload: Task 4.
- No backend, frontend, GUI, service, encryption, or duplicate-fingerprint changes are included.
- Plan avoids real upload commands.
