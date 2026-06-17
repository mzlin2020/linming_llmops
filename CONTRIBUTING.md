# 贡献指南 / Contributing

> Contributions are welcome — issues, bug reports, and pull requests. This guide (in Chinese) covers local setup, conventions, and the test gate.

感谢你对 `linming_llmops` 的关注，欢迎以 issue / PR 的形式参与。

## 本地开发环境

### 后端（`backend/`，Python 3.11+）

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
# requirements-ml.txt（torch / sentence-transformers）仅部署需要——
# 重 ML 依赖是懒加载的，测试套件用 fake_llm / fake_embeddings 夹具即可跑。
```

跑测试（本地用一次性 SQLite，无需 MySQL；CI 会在真实 MySQL/Redis/Qdrant 上复跑）：

```bash
SQLALCHEMY_DATABASE_URI="sqlite:////tmp/dev.db" JWT_SECRET="test-secret" AI_SECRET_ENCRYPT_KEY="test-secret" pytest
pytest tests/test_models.py            # 单文件
pytest -k "cascade"                    # 按名筛选
```

数据库迁移（`FLASK_APP=app.http.app`）：

```bash
flask db upgrade                       # 应用迁移
flask db migrate -m "msg"             # 自动生成（务必人工审阅）
```

### 前端（`frontend/`，Node 18+）

```bash
cd frontend
npm ci
npm run dev        # 开发服务器（代理 /api → 本地后端）
npm run test       # vitest
npm run typecheck  # tsc --noEmit
npm run build      # typecheck + vite build
```

### 全栈（Docker）

见 [`deploy/README.md`](deploy/README.md)。

## 提交约定

- **分支**：从 `main` 切功能分支（如 `feat/xxx`、`fix/xxx`），完成后提 PR。
- **提交信息**：建议 `type(scope): 摘要`（如 `feat(backend): ...`、`fix(frontend): ...`、`docs: ...`）。
- **测试为闸**：PR 必须保证后端 `pytest`、前端 `vitest` + `build` 全绿（CI 会校验，含全栈冒烟作业）。新增功能请补测试。
- **不提交密钥**：提交前自查 diff，确保没有真实 API key、口令、私有基础设施标识；`.env`、本地凭证均已 `.gitignore`，只提交 `.env.example`。

## 代码风格

- **后端**遵循既有接缝：handler 用 Pydantic schema 解析 → 调 service → 经 `pkg/response` 返回；service 用 `@inject @dataclass`，写操作用 `db.auto_commit()`；错误路径抛 `internal/exception/` 的类型化异常；新增模型从 `internal/model/__init__.py` 导出。
- **前端**沿用 `src/features/<module>/` 模块化结构，服务端状态用 TanStack Query、会话用 Zustand、表单用 react-hook-form + zod；请求体形状须与后端校验器逐字一致。
- 详细架构见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

## 行为准则

请保持友善、专业、就事论事。欢迎新人。
