"""对话 / SSE 链路的枚举常量。"""
from enum import Enum


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class InvokeFrom(str, Enum):
    """调用入口标识，用于后续区分埋点/计费"""
    WEB_APP = "web_app"
    PUBLISHED = "published"
    DEBUGGER = "debugger"
    API = "api"
    SERVICE_API = "service_api"
    ASSISTANT_AGENT = "assistant_agent"


class MessageStatus(str, Enum):
    """单条消息的最终状态"""
    NORMAL = "normal"
    STOP = "stop"
    TIMEOUT = "timeout"
    ERROR = "error"


class QueueEvent(str, Enum):
    """SSE 事件名。
    ping/message/agent_end/error/stop 为聊天链路实际下发；
    agent_thought（工具调用决策）/ agent_action（工具执行结果）由 Agent 运行时下发；
    timeout 预留。"""
    PING = "ping"
    MESSAGE = "message"
    AGENT_THOUGHT = "agent_thought"
    AGENT_ACTION = "agent_action"
    AGENT_END = "agent_end"
    ERROR = "error"
    STOP = "stop"
    TIMEOUT = "timeout"
    WORKFLOW = "workflow"  # 工作流调试：每节点一帧 NodeResult
