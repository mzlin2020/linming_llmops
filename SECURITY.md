# 安全说明 / Security

> Security notes for self-hosting `linming_llmops`: change the default credentials, manage the encryption key carefully, and report vulnerabilities privately.

## 部署前必改的默认凭证

`deploy/.env.example` 中的密钥类项目是**占位/空值**，生产部署前**必须**改成强随机值：

| 变量 | 说明 |
|---|---|
| `JWT_SECRET` | 登录令牌（access/refresh JWT，HS256）的签名密钥。泄漏即可伪造任意账号令牌。务必随机长串。 |
| `AI_SECRET_ENCRYPT_KEY` | provider/渠道 API Key **落库加密**的密钥材料（缺省回落 `JWT_SECRET`）。见下方轮换说明。 |
| `MYSQL_ROOT_PASSWORD` | 数据库口令。默认 `changeme`，**必改**。 |
| `QDRANT_API_KEY` | 向量库鉴权（默认空=不鉴权）。对外可达时建议设置。 |

生成随机值示例：`openssl rand -hex 32`。

## 密钥管理

- **`AI_SECRET_ENCRYPT_KEY` 一经使用请勿随意更换**：渠道/供应商的 API Key 以它派生的密钥（Fernet）加密存库。更换后**旧密文将无法解密**，需在后台重新填写所有渠道 key。
- 不要把真实 `.env`、令牌、私钥提交进版本库（仓库 `.gitignore` 已忽略 `.env`，仅提交 `.env.example`）。
- 默认存储为本地磁盘；上传文件落在容器卷中，注意宿主机文件权限与备份。

## 认证模型（设计取舍）

- 自包含**轻量登录**：单 `account` 表（邮箱 + 口令，werkzeug pbkdf2）+ 自签发 access/refresh **JWT(HS256)**。
- **无管理员 / 无 RBAC**：所有登录账号权限对等，配额对所有账号统一生效（按 env 配置）。这是有意简化——若需多租户隔离/细粒度权限，需自行在上层补充。
- 对外 **OpenAPI** 接口以 **API Key** 鉴权（前缀 `API_KEY_PREFIX`，默认 `ak-v1/`），与主站 JWT 鉴权分离。
- `ENABLE_LLM_ADMIN`（默认关）控制「模型目录写入面」——该面涉及全局共享凭证目录，仅在单运维可信部署下开启。
- 自助注册由 `ALLOW_REGISTRATION` 控制；对外暴露的实例建议关闭后改用预置账号（`BOOTSTRAP_ACCOUNT_*`）。

## 漏洞上报

如发现安全问题，请**不要**直接开公开 issue。优先通过 GitHub 的 **Private Vulnerability Reporting**（仓库 Security 标签页）私下上报；或以最小可复现信息私下联系维护者。我们会尽快响应并在修复后致谢。
