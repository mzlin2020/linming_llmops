"""ORM 模型聚合导出。

`from internal import model` 触发本模块，把全部表注册进 `db.metadata`——
Http 引擎与 Alembic env.py 都依赖它，autogenerate / create_all 才完整。
认证体系为自建 `account` 表（见 account.py），无 User/Role/Permission 镜像。
"""
from .account import Account
from .app import App, AppConfig, AppConfigVersion, PublicApp
from .conversation import Conversation, Message
from .message_agent_thought import MessageAgentThought
from .dataset import (
    Dataset,
    Document,
    Segment,
    KeywordTable,
    DatasetQuery,
    ProcessRule,
)
from .api_tool import ApiTool, ApiToolProvider, PublicPlugin
from .api_key import ApiKey, EndUser
from .upload_file import UploadFile
from .image import AiImage
from .llm_catalog import LlmProvider, LlmModel, LlmChannel
from .workflow import Workflow, WorkflowResult

__all__ = [
    # 认证账号
    "Account",
    # 应用编排
    "App", "AppConfig", "AppConfigVersion", "PublicApp",
    # 会话 / 消息
    "Conversation", "Message", "MessageAgentThought",
    # 知识库 / RAG
    "Dataset", "Document", "Segment", "KeywordTable", "DatasetQuery", "ProcessRule",
    # API 工具 / 插件
    "ApiTool", "ApiToolProvider", "PublicPlugin",
    # 开放 API
    "ApiKey", "EndUser",
    # 文件 / 图片
    "UploadFile", "AiImage",
    # 模型目录
    "LlmProvider", "LlmModel", "LlmChannel",
    # 工作流
    "Workflow", "WorkflowResult",
]
