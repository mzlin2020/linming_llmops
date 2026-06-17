# 供应商与模型配置指南 / Providers & Models

> How to configure LLM providers, the local embedding model, and optional image/TTS in `linming_llmops`. All values live in `deploy/.env.example`; copy it to `deploy/.env` and edit.

本文说明对话用的 **LLM 供应商**、知识库用的**本地嵌入模型**、以及可选的**图像/TTS**如何配置。所有变量在 [`deploy/.env.example`](../deploy/.env.example) 中分组列出。

---

## 1. LLM 供应商（对话 / Agent）

默认对接 **OpenAI 兼容**接口。可选其他供应商，均为 env-gated（不填即不启用）。

| 变量 | 说明 |
|---|---|
| `DEFAULT_LLM_PROVIDER` | 默认供应商，默认 `openai` |
| `DEFAULT_LLM_MODEL` | 默认模型，默认 `gpt-4o-mini` |
| `OPENAI_API_KEY` | OpenAI（或兼容服务）的 API Key |
| `OPENAI_BASE_URL` | 自建/中转的 OpenAI 兼容端点；留空走官方 |

### OpenAI / 兼容端点（默认）

```ini
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
# 用第三方兼容网关 / 自建推理服务时填其地址：
OPENAI_BASE_URL=https://your-gateway.example.com/v1
```

> 任何兼容 OpenAI Chat Completions 协议的服务（如各类中转、vLLM、Ollama 的 OpenAI 兼容端点等）都可经 `OPENAI_BASE_URL` 接入。

### Anthropic（可选）

```ini
ANTHROPIC_API_KEY=sk-ant-...
```

### DeepSeek（可选）

```ini
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### 火山方舟 Ark（可选，需中国账号）

```ini
VOLCENGINE_ARK_API_KEY=...
VOLCENGINE_ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v3
```

### 多渠道兜底熔断（仅 multi_channel provider 生效）

为同一模型配置多个渠道时，失败到阈值会临时熔断该渠道并切换：

```ini
CHANNEL_FAILURE_THRESHOLD=3      # 连续失败多少次后熔断
CHANNEL_COOLDOWN_SECONDS=300     # 熔断冷却秒数
```

### Agent 运行时

```ini
AGENT_MAX_ITERATIONS=5           # Agent 单次最多工具调用轮数
```

### 模型目录写入面开关

```ini
ENABLE_LLM_ADMIN=false           # 默认关；涉及全局共享凭证目录，仅可信单运维部署开启
API_KEY_PREFIX=ak-v1/            # OpenAPI 对外 Key 前缀（中性默认，可改）
```

---

## 2. 嵌入模型（知识库向量化，本地运行）

知识库的文档向量化与查询向量化使用**本地 `sentence-transformers`** 模型，**无需付费 key**。首次使用会把模型权重下载到缓存卷（Docker 部署下为 `hf-cache` 卷）。

| 变量 | 默认 | 说明 |
|---|---|---|
| `EMBEDDING_MODEL` | `BAAI/bge-small-zh-v1.5` | HuggingFace 模型名 |
| `EMBEDDING_VECTOR_SIZE` | `512` | 向量维度，**改模型必须同步改它并重建 collection** |
| `EMBEDDING_DEVICE` | `cpu` | `cpu` 或 `cuda` |
| `EMBEDDING_NORMALIZE` | `True` | 是否归一化向量 |
| `EMBEDDING_QUERY_INSTRUCTION` | （bge 中文指令） | 查询前缀指令（部分模型需要） |
| `HF_HOME` | 容器默认 | HuggingFace 缓存目录 |
| `HF_ENDPOINT` | 空（官方） | **国内下载慢/失败时**设 `https://hf-mirror.com` 走镜像 |

> Docker 部署须 `INSTALL_ML=true`（默认）才会装本地嵌入栈（torch / sentence-transformers）。设 `INSTALL_ML=false` 可得轻镜像，但知识库索引/检索不可用。

切换嵌入模型示例（注意同步维度并重建向量库 collection）：

```ini
EMBEDDING_MODEL=BAAI/bge-base-zh-v1.5
EMBEDDING_VECTOR_SIZE=768
```

---

## 3. 图像生成 / TTS（可选，v1.1）

**图像生成（v1.1，已交付）**：文生图 / 图生图，走 OpenAI 兼容的 `/images/generations`。供应商可插拔——`provider` 须先在「模型目录」里登记（含 `base_url` / `api_key` 凭证，与对话供应商同一套登记方式），再用下面两项指定默认生图 provider/model。**默认关闭**（留空即关），未配置时优雅降级；按张计费，成本由 `QUOTA_IMAGE_DAILY_LIMIT` 兜底。

```ini
# 图像（示例：OpenAI 兼容文生图）
DEFAULT_IMAGE_PROVIDER=openai
DEFAULT_IMAGE_MODEL=dall-e-3
```

生成的图片落本地存储，经不可猜的「能力 URL」`/api/images/file/<uuid>.<ext>` 对外（无需登录即可由 `<img>` 加载）。已发布的生图能力同时作为内置工具 `image_generation`，可被带工具的应用 Agent 在对话里调用。

**TTS（v1.1，进行中）**：供应商可插拔，**默认关闭**，前端界面与服务端处理器后续补齐（见 [`ROADMAP.md`](ROADMAP.md)）。

```ini
DEFAULT_TTS_PROVIDER=
DEFAULT_TTS_MODEL=
DEFAULT_TTS_VOICE=
```

---

## 凭证安全

渠道/供应商 API Key 落库时以 `AI_SECRET_ENCRYPT_KEY` 派生密钥加密。**请勿在使用后更换该密钥**，否则旧密文无法解密。详见 [`../SECURITY.md`](../SECURITY.md)。
