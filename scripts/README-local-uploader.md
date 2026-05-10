# 照片自动上传脚本使用教程

本文档说明如何使用 `photo-monitor-uploader.ps1` 在 Windows 上监控本地目录，并自动把新增照片上传到服务器。

脚本位置：

```text
scripts\photo-monitor-uploader.ps1
```

## 一、功能说明

脚本支持：

- 登录服务器并保存本地配置
- 持续监控指定目录
- 默认递归扫描所有子目录
- 自动上传新增照片
- 根据文件路径识别 `xiazhan` / `shangzhan`
- 上传成功后弹出 Windows 通知
- 自动避免重复上传
- 支持隐藏后台运行
- 支持开机自启

## 二、首次登录

首次使用前，需要先执行一次登录：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 login -WatchDir C:\Path\To\PhotoFolder
```

登录成功后，脚本会把服务器地址、用户、token、部门、监控目录等信息保存到本地配置文件。

默认服务器：

```text
http://121.43.132.227
```

如需显式指定账号、密码、部门：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 login -Server http://121.43.132.227 -Username <用户名> -Password <密码> -Department <部门名称> -WatchDir C:\Path\To\PhotoFolder
```

## 三、查看当前状态

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 status
```

状态会显示：

- 配置文件位置
- 日志文件位置
- 当前服务器
- 当前用户
- 当前部门
- 上传模式
- 监控目录
- 扫描间隔
- 文件稳定等待时间
- 是否递归扫描子目录
- 已上传记录数量

## 四、立即扫描一次

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 once
```

这个命令只扫描一次，适合测试当前配置是否正确。

如需只测试匹配文件，不真正上传：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 once -DryRun
```

## 五、后台隐藏运行

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 start-hidden -WatchDir C:\Path\To\PhotoFolder
```

`start-hidden` 会：

- 启动前检查登录配置是否有效
- 自动结束之前的旧上传进程
- 以隐藏窗口方式启动新的上传进程
- 按配置间隔持续扫描目录

如果命令中带了 `-WatchDir`、`-IntervalSeconds` 等参数，脚本会先写回本地配置，再启动后台进程。

## 六、开机自启

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 install-startup
```

该命令会在 Windows 启动项中创建快捷方式。下次开机登录 Windows 后，脚本会自动以隐藏方式运行。

## 七、测试通知

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 test-notification
```

如果通知功能正常，会看到 Windows 通知或托盘气泡。

上传成功时，通知内容类似：

```text
照片上传成功
xxx.jpg 已上传到 shangzhan
```

## 八、常用参数

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `-Server` | 后端服务器地址 | `http://121.43.132.227` |
| `-Username` | 登录用户名 | `<用户名>` |
| `-Password` | 登录密码 | `<密码>` |
| `-Department` | 上传部门 | 登录用户部门或手动输入 |
| `-Station` | 默认站点，路径中没有 `xiazhan` / `shangzhan` 时使用 | `uploads` |
| `-WatchDir` | 本地监控目录 | 脚本默认目录 |
| `-IntervalSeconds` | 持续监控扫描间隔 | `60` |
| `-StableSeconds` | 文件稳定等待时间 | `10` |
| `-TimeoutSeconds` | 请求超时时间 | `120` |
| `-NoSubdirectories` | 不扫描子目录 | 默认扫描子目录 |
| `-DryRun` | 只检测，不上传 | 默认关闭 |

## 九、照片上传说明

脚本只负责照片上传，只上传以下格式：

```text
.jpg .jpeg .png .webp
```

如果文件路径中包含：

```text
xiazhan
shangzhan
```

脚本会自动把照片上传到对应站点。

## 十、重复上传判断逻辑

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

上传成功后，脚本会把记录写入状态文件。

## 十一、本地文件位置

默认本地数据目录：

```text
%LOCALAPPDATA%\PhotoMonitorUploader
```

其中：

| 文件 | 说明 |
| --- | --- |
| `config.json` | 登录配置、token、监控目录 |
| `uploaded_state.json` | 已上传文件状态 |
| `uploader.log` | 运行日志 |

## 十二、查看日志

```powershell
Get-Content "$env:LOCALAPPDATA\PhotoMonitorUploader\uploader.log" -Tail 80
```

常见日志：

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

## 十三、重置上传状态

如果需要让脚本忘记已经上传过的文件，可以删除状态文件：

```powershell
Remove-Item "$env:LOCALAPPDATA\PhotoMonitorUploader\uploaded_state.json" -Force
```

注意：删除后，下次扫描可能会重新上传当前目录中的文件。

## 十四、常见问题

### 1. 修改脚本里的默认目录后，为什么后台仍然监控旧目录？

脚本运行时优先读取：

```text
%LOCALAPPDATA%\PhotoMonitorUploader\config.json
```

如果已经登录过，配置文件里的 `watch_dir` 会覆盖脚本默认值。

解决方式：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 login -WatchDir C:\Path\To\PhotoFolder
```

或：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 start-hidden -WatchDir C:\Path\To\PhotoFolder
```

### 2. 提示登录失效怎么办？

重新执行 `login`：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 login -WatchDir C:\Path\To\PhotoFolder
```

### 3. 提示目录不存在怎么办？

先确认目录真实存在，再重新指定：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 status -WatchDir C:\Path\To\PhotoFolder
```

### 4. 没有通知怎么办？

先测试通知：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 test-notification
```

如果仍不显示，检查 Windows 通知设置、勿扰模式或专注助手。

### 5. 上传失败 413 怎么办？

413 表示请求体太大，通常是服务器或 nginx 限制了上传大小。当前脚本会跳过超过 `200MB` 的文件；如果小于该限制仍出现 413，需要检查服务器 nginx 和后端上传限制。
