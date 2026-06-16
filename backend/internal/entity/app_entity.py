"""ai_app 的应用状态/配置类型枚举 + 默认配置 + 助手 Agent 常量。

DEFAULT_APP_CONFIG 的键名严格对齐配置表列名（model_config / dialog_round / tools / ...），
新建应用时写入 ai_app_config_version 的草稿行（config_type=draft, version=0）。
"""
import os
from enum import Enum


class AppStatus(str, Enum):
    """应用状态。草稿 = 仅有草稿配置未发布；已发布 = app_config_id 指向运行配置。"""

    DRAFT = "draft"
    PUBLISHED = "published"


class AppConfigType(str, Enum):
    """ai_app_config_version 的配置类型。草稿恒为 version=0 的一条；发布历史 version 递增。"""

    DRAFT = "draft"
    PUBLISHED = "published"


# 全局辅助 Agent 的统一人设。所有访客面对同一个助手。
# 可用环境变量 ASSISTANT_AGENT_PRESET_PROMPT 覆盖；改这里或环境变量后，
# get_or_create_assistant_agent_app 会在下次请求时把已存内置 app 的 preset 同步过去，无需删表重建。
ASSISTANT_AGENT_PRESET_PROMPT: str = os.getenv(
    "ASSISTANT_AGENT_PRESET_PROMPT",
    """你是这个平台的通用 AI 助手。

你的目标不是机械回答问题，而是真正帮助用户解决问题、缓解困惑、获得启发。

请始终保持：温和但不讨好、专业但不生硬、真诚但不矫情、有观点但不傲慢。
多说人话，少用客服腔、模板话和「AI 式表达」。

回答问题时，优先思考：用户真正想解决什么、现在最困惑的点是什么、需要的是信息/建议/判断还是情绪支持。
不要急着堆知识，先理解问题本质。

你的回答应尽量：简洁清晰、有逻辑、可执行、有现实价值。
比起空泛道理，更重要的是给步骤、给建议、给优先级、给避坑提醒，告诉用户下一步该做什么。

对于技术问题，不要只解释 API 或概念，更要解释「为什么这样设计」「真实开发里怎么做」「有哪些坑」。
允许表达判断与观点，但避免绝对化。""",
)

# 全局辅助 Agent 的默认内置工具：网页搜索 + 当前时间。
# 与人设一样以代码为准——get_or_create_assistant_agent_app 建表时种入草稿、
# 之后每次请求与本常量漂移时就地同步草稿行（改这里下次请求即生效，不动会话/消息）。
# 形态须与 AppConfigService._validate_tools 的存储输出逐字一致（直接展开入库、不过校验）。
# 注：google_serper 构造需 SERPER_API_KEY（缺失时 ToolResolver 安全跳过该工具）；current_time 零依赖。
ASSISTANT_AGENT_DEFAULT_TOOLS: list = [
    {"type": "builtin_tool", "provider": {"name": "google"}, "tool": {"name": "google_serper", "params": {}}},
    {"type": "builtin_tool", "provider": {"name": "time"}, "tool": {"name": "current_time", "params": {}}},
]

# 新建应用未自定义图标时，从这组内置图标里随机挑一个作为默认头像。
# 存的是前端可直接 <img src> 的根相对路径，PNG 资源放在前端 SPA 的静态目录 public/app-icons/<name>.png，
# 同源直出，无需任何远程图片代理/优化器配置。
DEFAULT_APP_ICON_BASE: str = "/app-icons"
DEFAULT_APP_ICON_NAMES: tuple = (
    "cube", "document", "chat", "robot", "code",
    "workflow", "search", "database", "image", "plugin",
)
DEFAULT_APP_ICONS: tuple = tuple(
    f"{DEFAULT_APP_ICON_BASE}/{name}.png" for name in DEFAULT_APP_ICON_NAMES
)

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
