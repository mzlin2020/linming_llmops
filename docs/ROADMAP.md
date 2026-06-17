# 路线图 / Roadmap

> Delivery history and what's next. v1 is feature-complete and deployable; v1.1 adds the workflow editor, image generation, and TTS.

## 当前状态

**v1 已交付、全栈可部署**：基础设施 → 内置轻量登录 → 数据模型/迁移基线 → 核心 AI 引擎 → 服务/存储 → 前端 SPA → Docker 一键部署 → 开源发布。

依赖主线：
**基础设施 → 认证接缝 →（数据模型 → 迁移基线）→ 核心引擎 → 服务/存储 → 前端 → 一键部署 → 开源发布 →（v1.1：工作流/图像/TTS）**。每阶段以「累计测试全绿」为出口。

## 关键技术决策

- **身份方案**：内置轻量登录（自建 `account` 表 + 账号密码 + 自签发 JWT），无管理员概念，不做复杂 RBAC。
- **模型供应商**：OpenAI 兼容为默认；Anthropic / DeepSeek / 火山 Ark 为可选、env-gated；图像生成 / TTS 默认关闭。
- **存储**：本地磁盘默认；保留 S3/MinIO 适配器接口供 env 切换。
- **嵌入**：本地 `BAAI/bge-small-zh-v1.5`（CPU 友好），支持 `HF_ENDPOINT` 镜像加速。
- **默认栈**：后端 Flask + MySQL 8 + Redis + Celery + Qdrant；前端 Vite + React SPA（nginx 托管并反代）。

## 阶段总览

| 阶段 | 名称 | 目标 | 状态 |
|---|---|---|---|
| Phase 0 | 脚手架 + 基础设施 + 决策锁定 | 目录骨架；compose 起 MySQL/Redis/Qdrant；派生 `.env.example`；CI 骨架 | ✅ |
| Phase 1 | 后端骨架 + 轻量登录认证 | Flask 应用壳可启动；内置 JWT 登录；保留 `current_user` 接缝 | ✅ |
| Phase 2 | 数据模型 + 迁移基线 | 业务归属列改普通整型列；自建 `account` 表；压平为可自举基线 | ✅ |
| Phase 3 | 核心 AI 引擎 | `internal/core/*`（语言模型/嵌入/向量/agent/工具/文件解析）；供应商可配置 | ✅ |
| Phase 4 | 服务 + 处理器 + 自托管存储 | v1 服务/处理器/Celery；本地磁盘存储适配器；配额拍平 | ✅ |
| Phase 5 | 前端（Vite React SPA） | 核心 AI 界面 + 框架无关 POST-SSE | ✅ |
| Phase 6 | Docker 一键部署 + 集成硬化 | 全栈 compose；启动即迁移；端到端冒烟 | ✅ |
| Phase 7 | 开源打磨（v1 发布） | README/LICENSE/CONTRIBUTING/SECURITY/供应商指南；定稿 `.env.example` | ✅ |
| Phase 8 | v1.1：工作流 / 图像 / TTS | 工作流 + 可视化编辑器（✅）；图像生成 文生图/图生图（✅）；TTS 供应商可插拔（⏳） | 🚧 进行中 |

## v1 功能清单

应用编排 · 对话(SSE 流式) · RAG 知识库（文档导入 / 向量索引 / 命中检索）· 内置 & API 工具 · 助手 Agent · LLM 目录与管理 · OpenAPI 外部调用 · 文件上传与管理。

## v1.1 计划（Phase 8）

- **工作流可视化编辑器（✅ 已交付）**：`core/workflow` 引擎已接出服务/处理器/`/workflows` 路由（CRUD + 草稿/发布双轨 + 调试 SSE）+ 前端 `@xyflow/react` 图编辑器（建图 → 逐节点流式调试 → 发布 → 作为工具被应用调用）。代码节点对所有登录用户开放（见 [`../SECURITY.md`](../SECURITY.md)）。
- **图像生成（✅ 已交付）**：文生图 / 图生图（OpenAI 兼容 `/images/generations`）+ 独立生图页与历史画廊 + 内置生图工具（Agent 对话出图）。对所有登录用户开放、`QUOTA_IMAGE_DAILY_LIMIT` 成本兜底；图片走不可猜的能力 URL（`/api/images/file/<uuid>.<ext>`）。供应商可插拔，默认关闭、未配置优雅降级（见 [`../SECURITY.md`](../SECURITY.md)）。
- **TTS（文本转语音）（⏳ 进行中）**：供应商可插拔实现，默认关闭。

## 验证方式（v1 出口）

干净主机：`cp deploy/.env.example deploy/.env` → 填 LLM 凭证 → `docker compose up` → 走「注册 → 建应用 → SSE 对话 → 建知识库并 RAG 检索 → 绑定工具让 Agent 调用」全链路；后端 `pytest` 全绿、前端 `vitest` + 构建通过。
