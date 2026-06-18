import os
from typing import Any
from urllib.parse import quote_plus

from .default_config import DEFAULT_CONFIG


def _get_env(key: str) -> Any:
    return os.getenv(key, DEFAULT_CONFIG.get(key))


def _get_bool_env(key: str) -> bool:
    value = _get_env(key)
    if value is None:
        return False
    return str(value).lower() == "true"


def _build_mysql_uri() -> str:
    explicit = _get_env("SQLALCHEMY_DATABASE_URI")
    if explicit:
        return explicit
    user = _get_env("mysql_server_username") or "root"
    pwd = quote_plus(str(_get_env("mysql_server_password") or ""))
    host = _get_env("mysql_server_host") or "127.0.0.1"
    port = _get_env("mysql_server_port") or 3306
    db = _get_env("mysql_server_database") or "linming_llmops"
    return f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{db}?charset=utf8mb4"


class Config:
    def __init__(self):
        self.WTF_CSRF_ENABLED = _get_bool_env("WTF_CSRF_ENABLED")

        # SQLAlchemy
        self.SQLALCHEMY_DATABASE_URI = _build_mysql_uri()
        self.SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_size": int(_get_env("SQLALCHEMY_POOL_SIZE")),
            "pool_recycle": int(_get_env("SQLALCHEMY_POOL_RECYCLE")),
            "pool_pre_ping": True,
        }
        self.SQLALCHEMY_ECHO = _get_bool_env("SQLALCHEMY_ECHO")

        # JWT（自有签发，与任何外部系统无关）
        self.JWT_SECRET = _get_env("JWT_SECRET")
        self.JWT_ALGORITHM = _get_env("JWT_ALGORITHM") or "HS256"
        self.JWT_ACCESS_TOKEN_EXPIRES = int(_get_env("JWT_ACCESS_TOKEN_EXPIRES"))
        self.JWT_REFRESH_TOKEN_EXPIRES = int(_get_env("JWT_REFRESH_TOKEN_EXPIRES"))

        # 认证策略（自建轻量登录，无管理员概念）
        self.ALLOW_REGISTRATION = _get_bool_env("ALLOW_REGISTRATION")
        self.BOOTSTRAP_ACCOUNT_EMAIL = _get_env("BOOTSTRAP_ACCOUNT_EMAIL") or None
        self.BOOTSTRAP_ACCOUNT_PASSWORD = _get_env("BOOTSTRAP_ACCOUNT_PASSWORD") or None

        # Redis
        self.REDIS_HOST = _get_env("REDIS_HOST")
        self.REDIS_PORT = int(_get_env("REDIS_PORT"))
        self.REDIS_USERNAME = _get_env("REDIS_USERNAME") or None
        self.REDIS_PASSWORD = _get_env("REDIS_PASSWORD") or None
        self.REDIS_DB = int(_get_env("REDIS_DB"))
        self.REDIS_USE_SSL = _get_bool_env("REDIS_USE_SSL")

        # Celery
        redis_userpass = ""
        if self.REDIS_USERNAME or self.REDIS_PASSWORD:
            redis_userpass = f"{self.REDIS_USERNAME or ''}:{self.REDIS_PASSWORD or ''}@"
        self.CELERY = {
            "broker_url": f"redis://{redis_userpass}{self.REDIS_HOST}:{self.REDIS_PORT}/{int(_get_env('CELERY_BROKER_DB'))}",
            "result_backend": f"redis://{redis_userpass}{self.REDIS_HOST}:{self.REDIS_PORT}/{int(_get_env('CELERY_RESULT_BACKEND_DB'))}",
            "task_ignore_result": _get_bool_env("CELERY_TASK_IGNORE_RESULT"),
            "result_expires": int(_get_env("CELERY_RESULT_EXPIRES")),
            "broker_connection_retry_on_startup": _get_bool_env("CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP"),
        }

        # Qdrant
        self.QDRANT_HOST = _get_env("QDRANT_HOST")
        self.QDRANT_PORT = int(_get_env("QDRANT_PORT"))
        self.QDRANT_GRPC_PORT = int(_get_env("QDRANT_GRPC_PORT"))
        self.QDRANT_API_KEY = _get_env("QDRANT_API_KEY") or None
        self.QDRANT_PREFER_GRPC = _get_bool_env("QDRANT_PREFER_GRPC")
        self.QDRANT_DATASET_COLLECTION = _get_env("QDRANT_DATASET_COLLECTION")

        # Embedding（知识库；core 模块直接读 os.getenv，这里收进 app.config 便于排查/复用）
        self.EMBEDDING_MODEL = _get_env("EMBEDDING_MODEL")
        self.EMBEDDING_VECTOR_SIZE = int(_get_env("EMBEDDING_VECTOR_SIZE"))
        self.EMBEDDING_DEVICE = _get_env("EMBEDDING_DEVICE")
        self.EMBEDDING_NORMALIZE = _get_bool_env("EMBEDDING_NORMALIZE")
        self.EMBEDDING_QUERY_INSTRUCTION = _get_env("EMBEDDING_QUERY_INSTRUCTION") or ""
        self.EMBEDDING_QUERY_PROMPT_NAME = _get_env("EMBEDDING_QUERY_PROMPT_NAME") or None

        # 知识库文件存储 / 上传
        self.STORAGE_BACKEND = _get_env("STORAGE_BACKEND")
        self.STORAGE_ROOT = _get_env("STORAGE_ROOT")
        self.FILES_BASE_URL = _get_env("FILES_BASE_URL") or None
        self.UPLOAD_ALLOWED_EXTENSIONS = _get_env("UPLOAD_ALLOWED_EXTENSIONS")
        self.UPLOAD_MAX_SIZE = int(_get_env("UPLOAD_MAX_SIZE"))

        # HuggingFace 缓存 / 镜像：必须在 transformers 被 import 前生效，故这里直接写回环境变量
        for _hf_key in ("HF_HOME", "HF_ENDPOINT"):
            _hf_val = _get_env(_hf_key)
            if _hf_val and not os.getenv(_hf_key):
                os.environ[_hf_key] = str(_hf_val)

        # LLM
        self.OPENAI_API_KEY = _get_env("OPENAI_API_KEY")
        self.OPENAI_BASE_URL = _get_env("OPENAI_BASE_URL") or None
        self.DEFAULT_LLM_PROVIDER = _get_env("DEFAULT_LLM_PROVIDER")
        self.DEFAULT_LLM_MODEL = _get_env("DEFAULT_LLM_MODEL")

        # 落库 provider/渠道 API Key 的加密密钥材料（缺省回落 JWT_SECRET）
        self.AI_SECRET_ENCRYPT_KEY = _get_env("AI_SECRET_ENCRYPT_KEY")
        # 多渠道兜底熔断参数（仅 multi_channel provider）
        self.CHANNEL_FAILURE_THRESHOLD = int(_get_env("CHANNEL_FAILURE_THRESHOLD"))
        self.CHANNEL_COOLDOWN_SECONDS = int(_get_env("CHANNEL_COOLDOWN_SECONDS"))

        # 图像生成（可选，v1.1；未配置则功能关闭）
        self.DEFAULT_IMAGE_PROVIDER = _get_env("DEFAULT_IMAGE_PROVIDER")
        self.DEFAULT_IMAGE_MODEL = _get_env("DEFAULT_IMAGE_MODEL")

        # 图像生成每日上限（成本安全网）
        self.QUOTA_IMAGE_DAILY_LIMIT = int(_get_env("QUOTA_IMAGE_DAILY_LIMIT"))

        # Agent 运行时
        self.AGENT_MAX_ITERATIONS = int(_get_env("AGENT_MAX_ITERATIONS"))

        # 开放 API 历史轮数上限（仅约束 service_api 链路；调用方不可覆盖）
        self.OPENAPI_HISTORY_MAX_TURNS = int(_get_env("OPENAPI_HISTORY_MAX_TURNS"))
        # 开放 API 密钥前缀（中性默认，env 可改）
        self.API_KEY_PREFIX = _get_env("API_KEY_PREFIX")
        # AI 模型目录管理写入面开关（部署级特性开关，默认关）
        self.ENABLE_LLM_ADMIN = _get_bool_env("ENABLE_LLM_ADMIN")
        # 开机把 providers/ 下 YAML 内置目录幂等灌入 DB（默认开；与 ENABLE_LLM_ADMIN 相互独立）
        self.SEED_LLM_CATALOG = _get_bool_env("SEED_LLM_CATALOG")

        # 知识库配额/限流（无管理员概念，对所有账号统一生效）
        self.QUOTA_MAX_DATASETS_PER_USER = int(_get_env("QUOTA_MAX_DATASETS_PER_USER"))
        self.QUOTA_MAX_DOCS_PER_DATASET = int(_get_env("QUOTA_MAX_DOCS_PER_DATASET"))
        self.QUOTA_USER_UPLOAD_MAX_SIZE = int(_get_env("QUOTA_USER_UPLOAD_MAX_SIZE"))
        self.QUOTA_BUILD_DAILY_LIMIT = int(_get_env("QUOTA_BUILD_DAILY_LIMIT"))
        self.QUOTA_BUILD_COOLDOWN_SECONDS = int(_get_env("QUOTA_BUILD_COOLDOWN_SECONDS"))
        self.QUOTA_HIT_PER_MINUTE = int(_get_env("QUOTA_HIT_PER_MINUTE"))
        self.QUOTA_HIT_DAILY_LIMIT = int(_get_env("QUOTA_HIT_DAILY_LIMIT"))

        # 开放 API 聊天限流（按账号计）
        self.QUOTA_OPENAPI_PER_MINUTE = int(_get_env("QUOTA_OPENAPI_PER_MINUTE"))
        self.QUOTA_OPENAPI_DAILY_LIMIT = int(_get_env("QUOTA_OPENAPI_DAILY_LIMIT"))

        # AI 聊天附件（图片多模态 + 文档文本注入）
        self.CHAT_ATTACHMENT_URL_PREFIXES = _get_env("CHAT_ATTACHMENT_URL_PREFIXES")
        self.CHAT_MAX_IMAGES_PER_MESSAGE = int(_get_env("CHAT_MAX_IMAGES_PER_MESSAGE"))
        self.CHAT_MAX_FILES_PER_MESSAGE = int(_get_env("CHAT_MAX_FILES_PER_MESSAGE"))
        self.CHAT_DOC_DOWNLOAD_MAX_BYTES = int(_get_env("CHAT_DOC_DOWNLOAD_MAX_BYTES"))
        self.CHAT_DOC_TEXT_MAX_CHARS = int(_get_env("CHAT_DOC_TEXT_MAX_CHARS"))

        # 聊天附件配额（图片+文档合计 个/天）
        self.QUOTA_CHAT_ATTACHMENTS_PER_DAY = int(_get_env("QUOTA_CHAT_ATTACHMENTS_PER_DAY"))

        # 工作流（DAG 编排）：配额 + 运行边界
        self.QUOTA_MAX_WORKFLOWS_PER_USER = int(_get_env("QUOTA_MAX_WORKFLOWS_PER_USER"))
        self.QUOTA_WORKFLOW_DEBUG_DAILY_LIMIT = int(_get_env("QUOTA_WORKFLOW_DEBUG_DAILY_LIMIT"))
        self.WORKFLOW_MAX_NODES = int(_get_env("WORKFLOW_MAX_NODES"))
        self.WORKFLOW_HTTP_TIMEOUT = int(_get_env("WORKFLOW_HTTP_TIMEOUT"))
        self.WORKFLOW_HTTP_MAX_RESPONSE_BYTES = int(_get_env("WORKFLOW_HTTP_MAX_RESPONSE_BYTES"))
        self.WORKFLOW_LLM_MAX_TOKENS = int(_get_env("WORKFLOW_LLM_MAX_TOKENS"))
        self.WORKFLOW_CODE_TIMEOUT_SECONDS = int(_get_env("WORKFLOW_CODE_TIMEOUT_SECONDS"))
        self.WORKFLOW_CODE_MAX_OUTPUT_BYTES = int(_get_env("WORKFLOW_CODE_MAX_OUTPUT_BYTES"))
