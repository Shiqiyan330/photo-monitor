# 照片自动上传脚本使用教程

本文说明如何使用 `scripts\photo-monitor-uploader.ps1` 在 Windows 上监控本地目录，并自动把新增照片上传到服务器。

## 功能

- 登录服务器并保存本地配置
- 持续扫描指定目录，默认递归扫描子目录
- 自动上传 `.jpg`、`.jpeg`、`.png`、`.webp`
- 根据路径中的 `xiazhan` / `shangzhan` 自动识别站点
- 上传成功后发送 Windows 通知
- 通过本地状态文件避免重复上传
- 支持失败重试、隐藏后台运行和开机自启
- 支持 `doctor` 诊断当前运行环境

## 首次登录

首次使用前，先执行一次登录：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 login -WatchDir C:\Path\To\PhotoFolder
```

登录成功后，脚本会把服务器地址、用户名、token、部门、监控目录等信息保存到本地配置文件。

如果需要显式指定账号、密码、部门或站点：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 login -Server http://121.43.132.227 -Username <用户名> -Password <密码> -Department <部门名称> -Station uploads -WatchDir C:\Path\To\PhotoFolder
```

默认服务器地址是：

```text
http://121.43.132.227
```

## 查看状态

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 status
```

状态会显示配置文件、日志文件、服务器、用户、部门、监控目录、扫描间隔、文件稳定等待时间、请求超时、上传重试次数、重试间隔、是否扫描子目录，以及已上传记录数量。

## 诊断环境

当上传没有按预期工作时，先运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 doctor
```

`doctor` 会检查：

- 本地配置文件是否存在
- 服务器地址格式是否有效
- 监控目录是否存在
- 登录 token 是否仍然可用
- 扫描、超时和重试设置
- 日志文件是否存在
- 当前是否有后台上传进程
- 最近日志中是否有 `error`、`failed`、`unauthorized`、`timeout` 等异常关键词

诊断输出不会显示保存的 token。

## 扫描一次

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 once
```

这个命令只扫描一次，适合测试当前配置是否正确。

只检查哪些文件会被处理，不真正上传：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 once -DryRun
```

`-DryRun` 仍会检查本地配置和监控目录，但不会上传文件。

## 后台隐藏运行

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 start-hidden -WatchDir C:\Path\To\PhotoFolder
```

`start-hidden` 会在启动前检查登录配置，自动结束之前的旧上传进程，并以隐藏窗口方式启动新的持续扫描进程。

如果命令中带有 `-WatchDir`、`-IntervalSeconds`、`-StableSeconds`、`-TimeoutSeconds`、`-RetryCount`、`-RetryDelaySeconds` 或 `-NoSubdirectories`，脚本会先写回本地配置，再启动后台进程。

## 持续前台运行

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 run
```

`run` 会持续扫描目录，适合排查问题时在终端里观察日志。生产使用通常建议用 `start-hidden`。

## 开机自启

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 install-startup
```

该命令会在 Windows 启动项中创建快捷方式。下次登录 Windows 后，脚本会自动以隐藏方式运行。

## 测试通知

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 test-notification
```

如果通知功能正常，会看到 Windows 通知或托盘气泡。上传成功时，通知内容会包含照片文件名和识别到的站点。

## 常用参数

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `-Server` | 后端服务器地址 | `http://121.43.132.227` |
| `-Username` | 登录用户名 | `admin` |
| `-Password` | 登录密码 | `admin` |
| `-Department` | 上传部门 | 登录用户部门或手动输入 |
| `-Station` | 默认站点，路径中没有 `xiazhan` / `shangzhan` 时使用 | `uploads` |
| `-WatchDir` | 本地监控目录 | 脚本默认目录 |
| `-IntervalSeconds` | 持续监控扫描间隔 | `60` |
| `-StableSeconds` | 文件稳定等待时间 | `10` |
| `-TimeoutSeconds` | 请求超时时间 | `120` |
| `-RetryCount` | 单个文件上传失败后的最多尝试次数 | `3` |
| `-RetryDelaySeconds` | 两次上传尝试之间的等待秒数 | `5` |
| `-TailLines` | `logs` 显示的最近日志行数 | `80` |
| `-NoSubdirectories` | 不扫描子目录 | 默认扫描子目录 |
| `-DryRun` | 只检测，不上传 | 默认关闭 |

## 照片上传规则

脚本只上传以下格式：

```text
.jpg .jpeg .png .webp
```

如果文件路径中包含 `xiazhan` 或 `shangzhan`，脚本会自动把照片上传到对应站点。否则使用 `-Station` 或配置文件中的默认站点。

超过 `200MB` 的文件会被跳过。

## 重复上传判断

脚本使用以下三项组成文件指纹：

```text
完整路径 + 文件大小 + 最后修改时间
```

只有当这个指纹没有出现在本地状态文件中时，脚本才会上传。

因此：

- 同路径、同大小、同修改时间：跳过
- 文件大小变化：重新上传
- 修改时间变化：重新上传
- 文件移动到新目录：重新上传
- 同名文件位于不同目录：视为不同文件

上传成功后，脚本会把记录写入本地状态文件。

## 本地文件位置

默认本地数据目录：

```text
%LOCALAPPDATA%\PhotoMonitorUploader
```

其中：

| 文件 | 说明 |
| --- | --- |
| `config.json` | 登录配置、token、监控目录和运行参数 |
| `uploaded_state.json` | 已上传文件状态 |
| `uploader.log` | 运行日志 |

如果设置了环境变量 `PHOTOMONITOR_UPLOADER_HOME`，脚本会优先把这些文件放到该目录。

## 查看日志

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 logs
```

自定义显示行数：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 logs -TailLines 120
```

也可以直接读取日志文件：

```powershell
Get-Content "$env:LOCALAPPDATA\PhotoMonitorUploader\uploader.log" -Tail 80
```

常见日志关键词：

```text
login check ok
uploader started
scan started
uploaded
scan complete
upload failed
notification shown
watch directory not found
```

## 重置上传状态

如果需要让脚本忘记已经上传过的文件，可以删除状态文件：

```powershell
Remove-Item "$env:LOCALAPPDATA\PhotoMonitorUploader\uploaded_state.json" -Force
```

删除后，下次扫描可能会重新上传当前目录中的文件。

## 常见问题

### 修改默认目录后，为什么后台仍然监控旧目录？

脚本运行时会优先读取：

```text
%LOCALAPPDATA%\PhotoMonitorUploader\config.json
```

如果已经登录过，配置文件里的 `watch_dir` 会覆盖脚本默认值。

重新指定目录：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 login -WatchDir C:\Path\To\PhotoFolder
```

或者：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 start-hidden -WatchDir C:\Path\To\PhotoFolder
```

### 提示登录失效怎么办？

重新执行 `login`：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 login -WatchDir C:\Path\To\PhotoFolder
```

### 提示目录不存在怎么办？

先确认目录真实存在，再重新指定：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 status -WatchDir C:\Path\To\PhotoFolder
```

### 没有通知怎么办？

先测试通知：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 test-notification
```

如果仍不显示，检查 Windows 通知设置、勿扰模式或专注助手。

### 上传失败 401 怎么办？

`401 Unauthorized` 通常表示本地 token 已失效。重新执行 `login` 后再运行 `doctor` 或 `once -DryRun`。

### 上传失败 413 怎么办？

`413` 表示请求体太大，通常是服务器或 nginx 限制了上传大小。脚本会跳过超过 `200MB` 的文件；如果小于该限制仍出现 `413`，需要检查服务器 nginx 和后端上传限制。
