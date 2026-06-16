"""Agent 运行时：基于 LangGraph 1.x 的 FunctionCallAgent（llm ⇄ tools 循环）。

本轮仅落地 FunctionCallAgent（依赖模型原生 tool_call）；ReActAgent（无 tool_call 模型的
prompt 模拟）留后续。流式调度与 SSE 翻译在 internal/service/_agent_runtime.py。
"""
from .agents.function_call_agent import FunctionCallAgent
from .entities.agent_entity import DEFAULT_MAX_ITERATION_COUNT, AgentConfig, AgentState
from .tool_resolver import ToolResolver

__all__ = [
    "FunctionCallAgent",
    "AgentConfig",
    "AgentState",
    "DEFAULT_MAX_ITERATION_COUNT",
    "ToolResolver",
]
