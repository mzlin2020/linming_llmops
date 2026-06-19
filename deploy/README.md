# 一键部署（Docker 全栈）

干净主机上三条命令起完整栈：MySQL / Redis / Qdrant / 后端 API（gunicorn）/ Celery worker / 前端（nginx）。

## 快速开始

```bash
cp deploy/.env.example deploy/.env
# 编辑 deploy/.env，至少改这几项：
#   JWT_SECRET、AI_SECRET_ENCRYPT_KEY、MYSQL_ROOT_PASSWORD  → 随机长串
#   OPENAI_API_KEY（或兼容端点 OPENAI_BASE_URL）           → 对话 / RAG 检索需要 LLM

docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
```

启动后浏览器打开 **http://127.0.0.1:8080**（端口由 `FRONTEND_PORT` 决定），注册账号即可使用。

> 首次启动较慢：后端/worker 镜像会安装本地 ML 嵌入栈（约 2GB），并在首次向量化时把嵌入模型权重（约 90MB）下载到 `hf-cache` 卷。之后重启会复用缓存。

## 需要改什么

| 变量 | 作用 | 生产是否必改 |
|---|---|---|
| `JWT_SECRET` | 登录令牌签名密钥 | ✅ 必改（随机长串） |
| `AI_SECRET_ENCRYPT_KEY` | provider/渠道 API Key 落库加密 | ✅ 必改（改后旧密文需重填） |
| `MYSQL_ROOT_PASSWORD` | 数据库密码 | ✅ 必改 |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | 对话 / RAG 检索的 LLM | 用对话/RAG 则填 |
| `FRONTEND_PORT` | 前端对外端口（默认 8080） | 按需 |
| `QDRANT_API_KEY` | 向量库鉴权（默认无） | 建议填 |

嵌入走本地模型，**RAG 索引/检索本身不需要付费 key**。

> **基础设施连接已在 compose 内固定。** 应用连 MySQL / Redis / Qdrant 的 host / port / 库号都是容器网络内的固定值，写死在 `docker-compose.yml` 的 `backend` / `celery-worker` 服务里，一键部署下**不经 `.env` 配置**；数据库密码也只由 `MYSQL_ROOT_PASSWORD` 决定（app 侧自动复用，不必再填 `mysql_server_password`）。

## 完整变量参考

精简版 `.env.example` 只列了必填与最常用项。下面是所有可调项及其默认值——**全部留空即用默认**，仅在需要细调时才填。默认值的真源是 `backend/config/default_config.py`。

### 认证 / 会话

| 变量 | 默认 | 说明 |
|---|---|---|
| `JWT_ACCESS_TOKEN_EXPIRES` | `604800` | access 令牌有效期（秒，7 天） |
| `JWT_REFRESH_TOKEN_EXPIRES` | `2592000` | refresh 令牌有效期（秒，30 天） |
| `JWT_ALGORITHM` | `HS256` | JWT 签名算法 |
| `ALLOW_REGISTRATION` | `true` | 是否开放自助注册；关闭后仅已存在/预置账号可登录 |
| `BOOTSTRAP_ACCOUNT_EMAIL` / `_PASSWORD` | 空 | 设了则首启迁移后幂等创建一个种子账号 |
| `WTF_CSRF_ENABLED` | `False` | CSRF 保护（纯 API + JWT 场景默认关） |

### LLM 供应商 / 模型目录

| 变量 | 默认 | 说明 |
|---|---|---|
| `DEFAULT_LLM_PROVIDER` | `openai` | 默认供应商（切换走模型管理 UI / 此处） |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek 官方端点 |
| `VOLCENGINE_ARK_API_KEY` / `_BASE_URL` | 空 / Ark 端点 | 火山方舟（需中国账号；不填不启用） |
| `CUSTOM_LLM_API_KEY` / `_BASE_URL` | 空 | 通用「OpenAI 兼容网关」内置 provider 凭证（默认禁用，设置→模型 里启用） |
| `SEED_LLM_CATALOG` | `true` | 开机把内置 YAML 模型目录幂等灌库（按名跳过已存在，不覆盖改动） |
| `CHANNEL_FAILURE_THRESHOLD` | `3` | 多渠道兜底熔断阈值（仅 multi_channel provider） |
| `CHANNEL_COOLDOWN_SECONDS` | `300` | 熔断冷却秒数 |
| `AGENT_MAX_ITERATIONS` | `5` | Agent 单次运行最大迭代步数 |

### 嵌入（本地向量化）

| 变量 | 默认 | 说明 |
|---|---|---|
| `EMBEDDING_MODEL` | `BAAI/bge-small-zh-v1.5` | 嵌入模型；改它须同步改 `EMBEDDING_VECTOR_SIZE` 并重建 collection |
| `EMBEDDING_VECTOR_SIZE` | `512` | 向量维度（须与模型匹配） |
| `EMBEDDING_DEVICE` | `cpu` | 推理设备 |
| `EMBEDDING_NORMALIZE` | `True` | 是否归一化向量 |
| `EMBEDDING_QUERY_INSTRUCTION` | 中文检索指令 | 查询前缀指令（bge 系列需要） |
| `EMBEDDING_WARMUP` | `true` | 进程启动时预热嵌入模型，消除「首次检索很慢」 |
| `HF_HOME` | 空 | HuggingFace 缓存目录（留空用容器默认） |

### 配额 / 限流（无管理员概念，对所有账号统一；`<=0` = 不限）

| 变量 | 默认 | 说明 |
|---|---|---|
| `QUOTA_MAX_DATASETS_PER_USER` | `3` | 每账号最多知识库数 |
| `QUOTA_MAX_DOCS_PER_DATASET` | `5` | 每知识库最多文档数 |
| `QUOTA_USER_UPLOAD_MAX_SIZE` | `2097152` | 单次上传上限（字节，2MB） |
| `QUOTA_BUILD_DAILY_LIMIT` | `3` | 每日建库/索引次数上限 |
| `QUOTA_BUILD_COOLDOWN_SECONDS` | `600` | 两次建库冷却秒数 |
| `QUOTA_HIT_PER_MINUTE` / `_DAILY_LIMIT` | `10` / `100` | 命中测试每分钟/每日上限 |
| `QUOTA_OPENAPI_PER_MINUTE` / `_DAILY_LIMIT` | `10` / `30` | 开放 API 聊天每分钟/每日上限 |
| `QUOTA_CHAT_ATTACHMENTS_PER_DAY` | `2` | 每日聊天附件次数 |
| `QUOTA_MAX_WORKFLOWS_PER_USER` | `3` | 每账号最多工作流数 |
| `QUOTA_WORKFLOW_DEBUG_DAILY_LIMIT` | `20` | 每日工作流调试次数 |
| `QUOTA_IMAGE_DAILY_LIMIT` | `100` | 每日生图次数（图像生成启用时） |

### 聊天附件（图片多模态 + 文档文本注入）

| 变量 | 默认 | 说明 |
|---|---|---|
| `CHAT_MAX_IMAGES_PER_MESSAGE` | `3` | 单条消息最多图片数 |
| `CHAT_MAX_FILES_PER_MESSAGE` | `2` | 单条消息最多文档数 |
| `CHAT_DOC_DOWNLOAD_MAX_BYTES` | `10485760` | 文档下载上限（字节，10MB） |
| `CHAT_DOC_TEXT_MAX_CHARS` | `20000` | 注入正文最大字符数 |
| `CHAT_ATTACHMENT_URL_PREFIXES` | 空 | 外部附件 URL 白名单前缀（逗号分隔；空=不放行任何外部 URL） |

### 工作流（可视化 DAG 运行边界）

| 变量 | 默认 | 说明 |
|---|---|---|
| `WORKFLOW_MAX_NODES` | `20` | 单工作流最大节点数 |
| `WORKFLOW_HTTP_TIMEOUT` | `10` | HTTP 节点超时秒数 |
| `WORKFLOW_HTTP_MAX_RESPONSE_BYTES` | `1048576` | HTTP 节点响应上限（1MB） |
| `WORKFLOW_LLM_MAX_TOKENS` | `1024` | LLM 节点最大输出 token |
| `WORKFLOW_CODE_TIMEOUT_SECONDS` | `5` | 代码节点超时秒数 |
| `WORKFLOW_CODE_MAX_OUTPUT_BYTES` | `65536` | 代码节点输出上限（64KB） |

### 存储 / 上传

| 变量 | 默认 | 说明 |
|---|---|---|
| `STORAGE_BACKEND` | `local` | 存储后端（`local`；S3/MinIO 为接口预留位） |
| `STORAGE_ROOT` | `storage` | 本地存储根目录 |
| `FILES_BASE_URL` | 空 | 对外文件基地址（`/files` 静态路由用） |
| `UPLOAD_ALLOWED_EXTENSIONS` | `txt,md,markdown,pdf,docx,csv,xlsx` | 允许上传的扩展名 |
| `UPLOAD_MAX_SIZE` | `15728640` | 上传硬上限（字节，15MB） |

### 运行时（进程 / 并发）

| 变量 | 默认 | 说明 |
|---|---|---|
| `SERVER_WORKER_AMOUNT` | `2` | gunicorn worker 数 |
| `SERVER_WORKER_CLASS` | `gthread` | gunicorn worker 类型 |
| `SERVER_THREAD_AMOUNT` | `4` | 每 worker 线程数 |
| `GUNICORN_TIMEOUT` | `600` | 请求超时秒数（SSE 长连接需较大值） |
| `CELERY_CONCURRENCY` | `5` | Celery worker 并发数 |
| `CELERY_POOL` | `prefork` | Celery 进程池类型 |
| `CELERY_LOG_LEVEL` | `INFO` | Celery 日志级别 |
| `SQLALCHEMY_POOL_SIZE` | `30` | DB 连接池大小 |

### 图像生成 / TTS（v1.1，默认关闭）

| 变量 | 默认 | 说明 |
|---|---|---|
| `DEFAULT_IMAGE_PROVIDER` / `_MODEL` | 空 | 文生图供应商/模型（须先在模型目录登记凭证；留空即关闭） |
| `DEFAULT_TTS_PROVIDER` / `_MODEL` / `_VOICE` | 空 | 文本转语音（规划中；留空即关闭） |

## 国内加速（可选）

下载/构建慢时在 `deploy/.env` 设镜像：

```ini
HF_ENDPOINT=https://hf-mirror.com                       # 嵌入模型走 HF 镜像
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple  # 构建期 pip 镜像
# TORCH_INDEX_URL 默认已是官方 CPU wheel 源，可按需替换
```

## 端到端冒烟

栈起来后跑：

```bash
bash deploy/smoke-test.sh
```

覆盖：就绪检查 → 注册/登录 → 建应用 → SSE 对话* → 建知识库 → 上传 → 索引 → RAG 检索。
（*SSE 对话步骤仅在设置了 `OPENAI_API_KEY` 时执行；其余步骤本地嵌入即可，无需付费 key。）

### 验证 SSE 不缓冲（R4）

冒烟脚本经前端 nginx 打 SSE，断言响应头含 `X-Accel-Buffering: no`。手动自查：

```bash
curl -N -D - -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"query":"你好"}' http://127.0.0.1:8080/api/apps/<app_id>/conversations
```

应看到响应头 `X-Accel-Buffering: no`，且 `data:` 帧逐条实时到达（非一次性返回）。

## 服务、端口与卷

| 服务 | 说明 | 对外端口（默认，仅本机） |
|---|---|---|
| `frontend` | nginx 静态托管 + 反代 `/api`（SSE 不缓冲） | `127.0.0.1:8080` |
| `backend` | Flask API（gunicorn），启动即迁移 | `127.0.0.1:5001` |
| `celery-worker` | 知识库索引 / 文档解析 / 异步任务 | — |
| `mysql` / `redis` / `qdrant` | 数据 / 缓存+队列 / 向量库 | 3306 / 6379 / 6333,6334 |

持久卷：`mysql-data`、`redis-data`、`qdrant-data`、`storage-data`（上传文件，backend 与 worker 共享）、`hf-cache`（嵌入模型权重）。

## 运维

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/.env ps          # 状态（mysql/redis 应 healthy）
docker compose -f deploy/docker-compose.yml --env-file deploy/.env logs -f backend
docker compose -f deploy/docker-compose.yml --env-file deploy/.env down         # 停（留数据）
docker compose -f deploy/docker-compose.yml --env-file deploy/.env down -v      # 停并清数据卷
```

## 轻量模式（不用本地 RAG）

只想用对话、不需要本地向量化检索时，可在 `.env` 设 `INSTALL_ML=false` 构建轻镜像（无 torch，启动快）。此时知识库的索引/检索不可用。

## 备注

- S3/MinIO 存储后端为接口预留位（当前 `STORAGE_BACKEND=local`），随适配器实现接入。
- 可视化工作流编辑器为 v1.1 已交付能力，本部署默认启用（无需额外开关）。
- 图像生成 / TTS 属 v1.1 后续能力，本部署默认不启用。
