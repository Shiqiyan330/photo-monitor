# 短信提醒配置说明

本项目支持两类阿里云短信通知：

- 员工生日祝福
- 员工证书到期前复审提醒

短信发送由后端统一判断。前端只负责维护员工手机号、生日、身份证号和证书有效期。

## 1. 安装依赖

后端依赖已写入 `photo-backend/requirements.txt`：

```text
alibabacloud_dysmsapi20170525==4.5.1
alibabacloud_credentials
alibabacloud_tea_openapi
alibabacloud_tea_util
python-dotenv
```

部署前执行：

```bash
pip install -r photo-backend/requirements.txt
```

## 2. 配置 `.env`

复制 `.env.example` 为 `.env`，然后填写真实配置。

```env
PHOTO_MONITOR_JWT_SECRET=change-me
SMS_ENABLED=false
ALIYUN_SMS_SIGN_NAME=浙江越岚索道管理
ALIYUN_SMS_BIRTHDAY_TEMPLATE_CODE=SMS_506865121
ALIYUN_SMS_CERT_TEMPLATE_CODE=SMS_506860107
SMS_DAILY_SEND_TIME=09:00
SMS_CERT_REMIND_DAYS_BEFORE=90
SMS_LOG_FILE=office_data/sms_logs.json
ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
```

`.env` 已被 `.gitignore` 忽略，不能提交真实密钥。

## 3. 模板映射

生日短信：

- 模板 CODE：`SMS_506865121`
- 签名：`浙江越岚索道管理`
- 模板变量：`name`
- 发送规则：生日当天发送。员工资料里手填生日优先；未填写时从 18 位身份证号解析生日。

证书复审短信：

- 模板 CODE：`SMS_506860107`
- 签名：`浙江越岚索道管理`
- 模板变量：`name`、`certName`、`dueDate`
- 发送规则：证书到期前 `SMS_CERT_REMIND_DAYS_BEFORE` 天发送，默认 90 天。

## 4. 干跑模式

默认配置为：

```env
SMS_ENABLED=false
```

此时系统会生成短信发送日志，但不会调用阿里云真实发送接口。建议上线前先保持干跑模式，检查日志内容。

管理员可手动触发一次扫描：

```http
POST /admin/sms/run-reminders
Authorization: Bearer <admin-token>
```

查看最近短信日志：

```http
GET /admin/sms/logs
Authorization: Bearer <admin-token>
```

日志默认保存到：

```text
photo-backend/office_data/sms_logs.json
```

## 5. 开启真实发送

确认以下内容后再开启：

- 阿里云 AccessKey 已填入运行环境。
- 短信签名 `浙江越岚索道管理` 状态正常。
- 两条模板 CODE 与变量名和本文一致。
- 员工手机号、生日、身份证号、证书有效期已核对。
- 干跑日志确认无误。

开启真实发送：

```env
SMS_ENABLED=true
```

建议先使用一个测试员工手机号做小范围验证，再开启全量员工自动提醒。

## 6. Docker 部署说明

Docker 部署时需要把 `.env` 中的变量传入后端容器。可选方式：

- 在 compose 中使用 `env_file: .env`
- 或在服务器环境变量中逐项配置

如果使用 `env_file`，确认 `.env` 位于 compose 执行目录，且不会被提交到 Git。

