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

## 工作流代码节点

- 工作流的 **Python 代码节点** 在三层沙箱中执行：stdlib AST 静态检查（拒危险调用）→ 受限内置 → 子进程 + 资源限制（`WORKFLOW_CODE_TIMEOUT_SECONDS` / `WORKFLOW_CODE_MAX_OUTPUT_BYTES`）。
- 因本平台**无管理员概念**，代码节点对**所有登录用户**开放（工作流校验按 `is_admin=True` 放行）；同样地，工作流内可使用标记 `admin_only` 的内置工具。沙箱是**纵深防御而非绝对边界**。
- 面向不可信用户开放注册的实例，建议据此评估风险：关闭自助注册（`ALLOW_REGISTRATION=false`）、做网络隔离，或在受信任的单运维部署下使用。

## 图像生成

- 图像生成按张计费、成本敏感。因本平台**无管理员概念**，该能力对**所有登录用户**开放（解除了原系统的管理员闸；内置生图工具 `admin_only=false`），成本由 `QUOTA_IMAGE_DAILY_LIMIT`（每日每账号上限，`<=0` 不限，redis fail-open）兜底；未配置生图模型（`DEFAULT_IMAGE_PROVIDER`/`DEFAULT_IMAGE_MODEL` 留空）时整能力关闭。
- 生成图片经后端「能力 URL」对外：路径含不可猜的随机 uuid（`/api/images/file/<uuid>.<ext>`），无需登录即可加载（供 `<img>` / Agent markdown 渲染），等价于对象存储的预签名公网 URL —— 按 uuid 能力授权，并对文件名做严格白名单校验（拒路径穿越）。图生图的参考图 URL 须过域名白名单 + SSRF 守卫。

## 漏洞上报

如发现安全问题，请**不要**直接开公开 issue。优先通过 GitHub 的 **Private Vulnerability Reporting**（仓库 Security 标签页）私下上报；或以最小可复现信息私下联系维护者。我们会尽快响应并在修复后致谢。
