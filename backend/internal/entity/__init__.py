"""业务实体（枚举 / 默认配置 / 轻量 schema）。模型与 core 通过全路径 import 各自模块；
service 层多从本聚合器 import。"""
from .ai_entity import (
    CONVERSATION_NAME_TEMPLATE,
    OPENING_QUESTIONS_TEMPLATE,
    OPTIMIZE_PROMPT_TEMPLATE,
    SUGGESTED_QUESTIONS_TEMPLATE,
    SUMMARIZER_TEMPLATE,
)
from .app_entity import (
    ASSISTANT_AGENT_DEFAULT_TOOLS,
    ASSISTANT_AGENT_PRESET_PROMPT,
    DEFAULT_APP_CONFIG,
    DEFAULT_APP_ICONS,
    AppConfigType,
    AppStatus,
)
from .chat_entity import ChatRole, InvokeFrom, MessageStatus, QueueEvent
from .workflow_entity import (
    DEFAULT_WORKFLOW_CONFIG,
    WORKFLOW_TOOL_NAME_PREFIX,
    WorkflowResultStatus,
    WorkflowStatus,
)
from .dataset_entity import (
    DEFAULT_MAX_KEYWORD_PER_CHUNK,
    DEFAULT_PROCESS_RULE,
    DEFAULT_RETRIEVAL_K,
    DEFAULT_RETRIEVAL_SCORE,
    DocumentStatus,
    ProcessType,
    RetrievalSource,
    RetrievalStrategy,
    SegmentStatus,
)

__all__ = [
    # 对话 / SSE
    "ChatRole",
    "InvokeFrom",
    "MessageStatus",
    "QueueEvent",
    # 知识库 / RAG
    "RetrievalStrategy",
    "RetrievalSource",
    "ProcessType",
    "DocumentStatus",
    "SegmentStatus",
    "DEFAULT_PROCESS_RULE",
    "DEFAULT_MAX_KEYWORD_PER_CHUNK",
    "DEFAULT_RETRIEVAL_K",
    "DEFAULT_RETRIEVAL_SCORE",
    # 应用编排
    "DEFAULT_APP_CONFIG",
    "DEFAULT_APP_ICONS",
    "ASSISTANT_AGENT_PRESET_PROMPT",
    "ASSISTANT_AGENT_DEFAULT_TOOLS",
    "AppStatus",
    "AppConfigType",
    # AI 辅助 / 长期记忆模板
    "SUMMARIZER_TEMPLATE",
    "CONVERSATION_NAME_TEMPLATE",
    "OPTIMIZE_PROMPT_TEMPLATE",
    "OPENING_QUESTIONS_TEMPLATE",
    "SUGGESTED_QUESTIONS_TEMPLATE",
    # 工作流
    "WorkflowStatus",
    "WorkflowResultStatus",
    "DEFAULT_WORKFLOW_CONFIG",
    "WORKFLOW_TOOL_NAME_PREFIX",
]
