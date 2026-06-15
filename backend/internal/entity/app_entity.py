"""ai_app 的应用状态/配置类型枚举 + 默认配置。

DEFAULT_APP_CONFIG 的键名严格对齐配置表列名（model_config / dialog_round / tools / ...），
新建应用时写入 ai_app_config_version 的草稿行（config_type=draft, version=0）。

注：助手 Agent 人设、默认图标等服务层常量随 AppService 在后续阶段移植，本期模型层不依赖。
"""
from enum import Enum


class AppStatus(str, Enum):
    """应用状态。草稿 = 仅有草稿配置未发布；已发布 = app_config_id 指向运行配置。"""

    DRAFT = "draft"
    PUBLISHED = "published"


class AppConfigType(str, Enum):
    """ai_app_config_version 的配置类型。草稿恒为 version=0 的一条；发布历史 version 递增。"""

    DRAFT = "draft"
    PUBLISHED = "published"


DEFAULT_APP_CONFIG: dict = {
    "model_config": {},
    "dialog_round": 3,
    "preset_prompt": "",
    # 新建应用默认挂一个零配置工具（获取当前时间），开箱即可在调试聊天验证工具链路。
    # 形态须与配置服务的工具存储输出逐字一致（建草稿时直接展开入库、不过校验）。
    "tools": [
        {"type": "builtin_tool", "provider": {"name": "time"}, "tool": {"name": "current_time", "params": {}}},
    ],
    "workflows": [],
    "datasets": [],
    "retrieval_config": {},
    "long_term_memory": {"enable": False},
    "opening_statement": "",
    "opening_questions": [],
    "speech_to_text": {"enable": False},
    "text_to_speech": {"enable": False},
    "suggested_after_answer": {"enable": True},
    "review_config": {},
}
