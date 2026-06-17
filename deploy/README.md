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
