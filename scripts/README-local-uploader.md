# 本地自动上传程序

这个程序用于在本地登录后常驻后台，定时扫描一个固定目录，把新增文件上传到后端 `/uploads` 接口。

## 1. 首次登录并保存配置

```powershell
python .\scripts\local_uploader.py login --server http://服务器地址:8000 --username 用户名 --watch-dir "D:\待上传目录" --department 部门名 --station uploads --interval 60
```

如果不写 `--password`，程序会安全地提示输入密码。登录成功后会把 token、部门、扫描目录和间隔保存到当前用户的本地配置目录。

## 2. 前台测试扫描一次

```powershell
python .\scripts\local_uploader.py once
```

## 3. 隐藏到后台运行

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-local-uploader-hidden.ps1
```

后台程序会每隔配置的秒数扫描一次目录，只上传还没有成功上传过、并且文件已经稳定超过 10 秒的文件。

## 4. 查看状态

```powershell
python .\scripts\local_uploader.py status
```

日志位置会在 `status` 输出里显示，通常在：

```text
%LOCALAPPDATA%\PhotoMonitorUploader\uploader.log
```
