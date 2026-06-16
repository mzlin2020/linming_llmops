# 应用默认配置项（env 未设置时回落到这里）
DEFAULT_CONFIG = {
    # WTF
    "WTF_CSRF_ENABLED": "False",

    # MySQL
    "mysql_server_host": "127.0.0.1",
    "mysql_server_port": "3306",
    "mysql_server_username": "root",
    "mysql_server_password": "",
    "mysql_server_database": "linming_llmops",

    # SQLAlchemy
    "SQLALCHEMY_DATABASE_URI": "",
    "SQLALCHEMY_POOL_SIZE": 30,
    "SQLALCHEMY_POOL_RECYCLE": 3600,
    "SQLALCHEMY_ECHO": "False",

    # JWT（自有签发）
    "JWT_SECRET": "",
    "JWT_ALGORITHM": "HS256",
    "JWT_ACCESS_TOKEN_EXPIRES": 604800,    # 7 天
    "JWT_REFRESH_TOKEN_EXPIRES": 2592000,  # 30 天

    # 认证策略（自建轻量登录，无管理员概念）
    "ALLOW_REGISTRATION": "true",
    "BOOTSTRAP_ACCOUNT_EMAIL": "",
    "BOOTSTRAP_ACCOUNT_PASSWORD": "",

    # Redis
    "REDIS_HOST": "127.0.0.1",
    "REDIS_PORT": 6379,
    "REDIS_USERNAME": "",
    "REDIS_PASSWORD": "",
    "REDIS_DB": 2,
    "REDIS_USE_SSL": "False",

    # Celery
    "CELERY_BROKER_DB": 3,
    "CELERY_RESULT_BACKEND_DB": 4,
    "CELERY_TASK_IGNORE_RESULT": "False",
    "CELERY_RESULT_EXPIRES": 3600,
    "CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP": "True",

    # Qdrant
    "QDRANT_HOST": "127.0.0.1",
    "QDRANT_PORT": 6333,
    "QDRANT_GRPC_PORT": 6334,
    "QDRANT_API_KEY": "",
    "QDRANT_PREFER_GRPC": "False",
    "QDRANT_DATASET_COLLECTION": "ai_dataset",

    # Embedding（知识库向量化，本地开源模型，sentence-transformers 加载）
    "EMBEDDING_MODEL": "BAAI/bge-small-zh-v1.5",
    "EMBEDDING_VECTOR_SIZE": 512,
    "EMBEDDING_DEVICE": "cpu",
    "EMBEDDING_NORMALIZE": "True",
    "EMBEDDING_QUERY_INSTRUCTION": "为这个句子生成表示以用于检索相关文章：",
    "EMBEDDING_QUERY_PROMPT_NAME": "",
    "HF_HOME": "",
    "HF_ENDPOINT": "",

    # 文件/图片存储（默认本地磁盘，存储适配器在 Phase 4 接线）
    "STORAGE_BACKEND": "local",
    "STORAGE_ROOT": "storage",
    "FILES_BASE_URL": "",
    "UPLOAD_ALLOWED_EXTENSIONS": "txt,md,markdown,pdf,docx,csv,xlsx",
    "UPLOAD_MAX_SIZE": 15728640,  # 15MB

    # LLM
    "OPENAI_API_KEY": "",
    "OPENAI_BASE_URL": "",
    "DEFAULT_LLM_PROVIDER": "openai",
    "DEFAULT_LLM_MODEL": "gpt-4o-mini",

    # 落库 provider/渠道 API Key 加密密钥材料（缺省回落 JWT_SECRET）
    "AI_SECRET_ENCRYPT_KEY": "",
    # 多渠道兜底熔断
    "CHANNEL_FAILURE_THRESHOLD": 3,
    "CHANNEL_COOLDOWN_SECONDS": 300,

    # 图像生成（可选，v1.1，默认关闭）
    "DEFAULT_IMAGE_PROVIDER": "volcengine_seedream",
    "DEFAULT_IMAGE_MODEL": "doubao-seedream-5-0-260128",
    "QUOTA_IMAGE_DAILY_LIMIT": 100,

    # Agent 运行时
    "AGENT_MAX_ITERATIONS": 5,

    # 开放 API 单次对话最多回溯的历史轮数（服务端变量，调用方不可覆盖）
    "OPENAPI_HISTORY_MAX_TURNS": 3,

    # 知识库配额/限流（无管理员概念，对所有账号统一）
    "QUOTA_MAX_DATASETS_PER_USER": 3,
    "QUOTA_MAX_DOCS_PER_DATASET": 5,
    "QUOTA_USER_UPLOAD_MAX_SIZE": 2097152,  # 2MB
    "QUOTA_BUILD_DAILY_LIMIT": 3,
    "QUOTA_BUILD_COOLDOWN_SECONDS": 600,
    "QUOTA_HIT_PER_MINUTE": 10,
    "QUOTA_HIT_DAILY_LIMIT": 100,

    # 开放 API 聊天限流（按账号计）
    "QUOTA_OPENAPI_PER_MINUTE": 10,
    "QUOTA_OPENAPI_DAILY_LIMIT": 30,

    # AI 聊天附件（图片多模态 + 文档文本注入）
    # 附件 URL 白名单前缀（逗号分隔）：默认空 = 不放行任何外部附件 URL，需显式配置允许的存储域前缀。
    "CHAT_ATTACHMENT_URL_PREFIXES": "",
    "CHAT_MAX_IMAGES_PER_MESSAGE": 3,
    "CHAT_MAX_FILES_PER_MESSAGE": 2,
    "CHAT_DOC_DOWNLOAD_MAX_BYTES": 10485760,  # 10MB
    "CHAT_DOC_TEXT_MAX_CHARS": 20000,
    "QUOTA_CHAT_ATTACHMENTS_PER_DAY": 2,

    # 工作流（DAG 编排）：配额 + 运行边界
    "QUOTA_MAX_WORKFLOWS_PER_USER": 3,
    "QUOTA_WORKFLOW_DEBUG_DAILY_LIMIT": 20,
    "WORKFLOW_MAX_NODES": 20,
    "WORKFLOW_HTTP_TIMEOUT": 10,
    "WORKFLOW_HTTP_MAX_RESPONSE_BYTES": 1048576,  # 1MB
    "WORKFLOW_LLM_MAX_TOKENS": 1024,
    "WORKFLOW_CODE_TIMEOUT_SECONDS": 5,
    "WORKFLOW_CODE_MAX_OUTPUT_BYTES": 65536,  # 64KB
}
