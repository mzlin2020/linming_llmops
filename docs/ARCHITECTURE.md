# 架构说明 / Architecture

> A high-level map of how `linming_llmops` is put together — backend, AI engine, frontend, and deployment. For per-variable configuration see [`PROVIDERS.md`](PROVIDERS.md) and `deploy/.env.example`.

本文勾勒整体架构，便于贡献者快速建立全局认识。

## 总览

```
浏览器 ──▶ frontend (nginx: React SPA + /api 反代, SSE 不缓冲)
                │ /api
                ▼
        backend (Flask + gunicorn) ──┐         celery-worker
         REST + POST-SSE             │          文档解析 / 向量索引 / 异步任务
         轻量登录(JWT) + OpenAPI     │              │
                │        │          │              │
                ▼        ▼          ▼              ▼
            MySQL 8    Redis      Qdrant   ◀── 共享存储卷(上传文件) + 嵌入模型缓存卷
            业务数据  缓存/队列   向量库
```

- 默认对接 **OpenAI 兼容** LLM；知识库向量化用**本地嵌入模型** `BAAI/bge-small-zh-v1.5`。
- `backend`（web）与 `celery-worker` 共享上传文件卷：web 保存上传 → worker 读取并索引；查询向量化发生在 web 进程的检索路径，故两者都需要 ML 依赖。

## 后端（`backend/`）

Flask 3.1，使用 **`injector` 依赖注入**：业务类多为 `@inject @dataclass`，依赖以类型化字段注入。

- **入口**：`app.http.app`（`FLASK_APP=app.http.app`）；Celery 入口 `app.http.app.celery`。
- **应用工厂**：`internal/server/http.py` 的 `class Http(Flask)`——加载配置、注册全局错误处理、初始化扩展（db/migrate/redis/celery/logging/login）、启用 CORS，再装中间件与路由。
- **依赖装配**：`app/http/module.py` 把扩展单例绑入一个 `Injector`，handler/service/router 经它解析。
- **请求流**：`internal/router/router.py` 在两个蓝图上注册路由——主 `/api`（JWT 鉴权）与 `/api/openapi`（API Key 鉴权，面向外部调用）。Handler（`internal/handler/`）用 **Pydantic schema**（`internal/schema/`）解析校验入参 → 调 **service**（`internal/service/`）→ 经 `pkg/response` 返回标准信封；service 持有业务逻辑与经模型（`internal/model/`）的 DB 访问。
- **请求期认证**：Flask-Login 的 `request_loader` 指向 `Middleware.request_loader`，按蓝图分支：`openapi` 用 API Key（key → `Account`），否则解码 Bearer access JWT → 载入 `Account`；两路均设置 `current_user`，无凭证即匿名。
- **错误处理**：抛 `internal/exception/` 的类型化异常（`FailException`/`NotFoundException`/`UnauthorizedException`/…），应用级处理器统一转成 JSON 信封。
- **自定义 SQLAlchemy**：`pkg/sqlalchemy` 提供 `db.auto_commit()` 上下文（成功提交/异常回滚），写操作优先用它。
- **配置**：`config/config.py` 纯从环境变量构建 `Config`（`config/default_config.py` 兜底）；`SQLALCHEMY_DATABASE_URI` 可由 `mysql_server_*` 拼装或整串覆盖（本地测试可指向 SQLite）。

### 自包含轻量登录（认证接缝）

平台不依赖外部用户网关，采用自包含登录：单 `account` 表（`Account`，`UserMixin`），邮箱+口令（werkzeug pbkdf2）+ 自签发 access/refresh JWT(HS256)，**无管理员、无 RBAC**。`current_user` 接缝稳定（`Account` 暴露 `is_admin → False`、`permission_codes → []`）；`@RequireLogin` 校验 JWT，`@RequirePermission(*codes)` 拍平为「仅登录」。业务归属列（`user_id`/`created_by` 等）是**普通索引整型列**，按 `current_user.id` 在应用层过滤。

### 核心 AI 引擎（`internal/core/`）

供应商可配置的引擎层：`language_model`、`embeddings`、`vector_store`、`retrievers`、`file_extractor`、`agent`、`tools`、`workflow`、`memory`、`mcp`。

- **`core/` 不感知认证**：归属（`user_id`）与恒假的 `is_admin` 作为普通参数传入。
- **重 ML 懒加载**：torch / sentence-transformers 在属性与任务体内才导入，导入 core 或启动 web 进程不会拉起 ML。
- `core/workflow` v1 仅提供库层（引擎），工作流的服务/处理器与可视化编辑器在 v1.1 暴露。

### 支撑层

- **`lib/`**：`crypto.py` 对落库的 provider/渠道 key 做 Fernet 加密（密钥材料来自 `AI_SECRET_ENCRYPT_KEY`，回落 `JWT_SECRET`）；`helper.py` 提供内置工具框架依赖的动态导入工具。
- **`storage/`**：`StorageService` 存储façade，后端由 `STORAGE_BACKEND` 选择（默认 `local`）；`s3`/`minio` 为接口预留。
- **`task/`**：Celery `ai.*` 任务（数据集/文档/会话）+ `worker_ready` 恢复钩子；任务体懒导入 ML。
- **配额**（`service/quota_service.py`）：无 `is_admin` 豁免，全部账号共享一套 env 驱动配额（`<=0`=不限），Redis 失败时 fail-open。

### 数据库与迁移

MySQL 8 为生产/CI 基准；迁移 MySQL-first（`render_as_batch=False`，发原生 `ALTER`/`CREATE INDEX`）。迁移在 `backend/internal/migration/`，基线两条：`0001_create_account` → `0002_create_ai_business_tables`（25 张 `ai_*` 表，无 `user.id` 外键）。空库经 `flask db upgrade` 自举；对最终模型 `flask db migrate` 应报「No changes detected」（无漂移）。

## 前端（`frontend/`）

Vite + React 18 + TypeScript 单页应用。服务端状态用 **TanStack Query**，会话用 **Zustand**，表单用 **react-hook-form + zod**，样式 Tailwind 3 + 手搭的 shadcn 风格原子组件。`@` 别名 `src/`，开发期 `/api` 代理到本地后端。

两条横切基座（均在 `src/lib/`）：

- **HTTP（`lib/http/`）**：单 axios 实例，响应拦截器**解包 `{code,message,data}` 信封**，`get<T>`/`post<T>` 直接拿到 `data`；`401` 触发**单飞刷新队列**（并发失败只发一次 `/auth/refresh` 再重放，刷新失败则硬登出）；错误统一为 `ApiError`。
- **SSE（`lib/sse/`）**：POST 无法用 `EventSource`，故 `streamSSE` 用 `fetch` POST + `ReadableStream`，注入 Bearer token；帧解析是**纯函数**（容忍分块/多帧/CRLF，做了字节级单测）；非 2xx 抛 `ApiError`，`AbortController` 取消静默吞掉。

结构：路由集中在 `routes/router.tsx`，受 `<RequireAuth>` 保护；功能模块在 `src/features/<module>/`（首页助手、插件、知识库、应用编排、设置、工作流占位）；共享对话核心 `features/chat/use-chat-stream.ts` 是通用流式 hook，首页助手与应用调试面板共用。**请求体形状与后端校验器逐字一致**。

## 部署（`deploy/`）

`docker-compose.yml` 编排六服务：`mysql` / `redis` / `qdrant` / `backend`(gunicorn) / `celery-worker` / `frontend`(nginx)，healthcheck 有序启动；`backend` 启动即迁移。后端镜像两段式，`INSTALL_ML` build-arg 控制是否装 CPU-only ML 栈；`backend` 与 `celery-worker` 共享上传文件卷与嵌入模型缓存卷。`frontend` 的 nginx 反代 `/api` 并**禁用缓冲**以支持 SSE 流式（`proxy_buffering off` / 长 `proxy_read_timeout` / `X-Accel-Buffering no`），upstream 经 envsubst 注入。

部署与冒烟见 [`../deploy/README.md`](../deploy/README.md)。
