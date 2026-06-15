# linming_llmops

目标：本项目是打算将/code目录下的linming项目的ai功能剥离为一个可开源的完整项目。

开发计划与规范
1、项目包括前端和后端。是一个完整的llmops项目
2、完全借鉴code/linming、code/linming_ai,除了用户与权限的逻辑。（如果有其他不适合移植或开源的也不应借鉴）
3、技术栈不完全借鉴（前端nextjs改为React，后端基本一致）
4、需要有完善的测试流程，每一阶段开发完毕都需要完整走测试
5、敏感信息全部抽离为可配置
6、开源项目届时需要抽取为非常方便用户运行。用户仅需填写.env配置，然后执行docker一键部署即可运行。
7、注意借鉴/code下项目代码时，不要改到/code下的代码。只读即可。


## 开发阶段划分

> 完整开发指导（背景、关键决策、解耦点、测试策略、风险登记）见 [`docs/开发指南.md`](docs/开发指南.md)。

### 已确定的关键决策
- **身份方案**：内置轻量登录（自建 `account` 表 + 账号密码），无管理员概念，排除复杂 RBAC。
- **模型供应商**：OpenAI 兼容为默认；Anthropic / 火山 Ark 为可选插件；图像生成 / TTS 默认关闭。
- **存储**：本地磁盘默认（替换原对网关服务 OSS 的委托），保留 S3/MinIO 适配器供 env 切换。
- **v1 范围**：核心优先（应用编排 + 对话/SSE + 知识库/RAG + 内置/API 工具 + 助手 agent）；工作流编辑器、图像、TTS 后置到 v1.1。
- 默认栈：后端 Flask + MySQL 8 + Redis + Celery + Qdrant；前端 Vite + React SPA（nginx 托管并反代）。

### 阶段总览
依赖主线：**基础设施 → 认证接缝 →（数据模型 → 迁移基线）→ 核心引擎 → 服务/存储 → 前端 → 一键部署 → 开源打磨 →（v1.1：工作流/图像/TTS）**。每阶段以「累计测试全绿」为出口。

| 阶段 | 名称 | 目标 |
|---|---|---|
| Phase 0 | 脚手架 + 基础设施 + 决策锁定 | 目录骨架；compose 起 MySQL/Redis/Qdrant；派生 `.env.example`；CI 骨架 |
| Phase 1 | 后端骨架 + 轻量登录认证 | Flask 应用壳可启动；自建登录替换原网关 JWT 耦合；保留 `current_user` 接缝 |
| Phase 2 | 数据模型 + 重建迁移基线 | 去 `user.id` 外键；自建 `account` 表；压平为单条可自举的 `0001_initial` |
| Phase 3 | 核心 AI 引擎移植 | `internal/core/*`（语言模型/嵌入/向量/agent/工具/文件解析）；供应商可配置 |
| Phase 4 | 服务+处理器移植 + 自托管存储 | v1 服务/处理器/Celery；本地磁盘存储适配器；配额拍平 |
| Phase 5 | 前端重写（Vite React SPA） | 核心 AI 界面 + 框架无关 POST-SSE；排除工作流/图像/TTS |
| Phase 6 | Docker 一键部署 + 集成硬化 | 全栈 compose；启动即迁移；端到端冒烟 |
| Phase 7 | 开源打磨（v1 发布） | README/LICENSE/`.env.example`/CONTRIBUTING；清除中国特有默认值 |
| Phase 8 | v1.1：工作流 + 图像 + TTS | 暴露工作流引擎 + xyflow 编辑器；图像/TTS 供应商可插拔 |
