"""Agent 运行时的状态与配置实体（LangGraph 1.x）。

- AgentState：在 LangGraph 内置 MessagesState（messages + add_messages reducer）之上
  加迭代计数，用于约束 llm ⇄ tools 的循环轮数。
- AgentConfig：FunctionCallAgent 运行所需的最小配置。preset_prompt / 历史消息已经在
  入参 messages 里（由 _chat_common.build_lc_messages 拼好），故此处不再重复携带。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langgraph.graph import MessagesState

# 默认最大工具调用轮数；env AGENT_MAX_ITERATIONS 可覆盖（见 _agent_runtime.max_iteration_count）。
DEFAULT_MAX_ITERATION_COUNT = 5


class AgentState(MessagesState):
    """LangGraph 状态：messages（带 add_messages reducer）+ 迭代计数。
    迭代上限读 AgentConfig.max_iteration_count（节点逻辑用它），不入 state。"""

    iteration_count: int


@dataclass
class AgentConfig:
    """FunctionCallAgent 的最小运行配置。"""

    tools: list[Any] = field(default_factory=list)
    tool_call_supported: bool = False
    max_iteration_count: int = DEFAULT_MAX_ITERATION_COUNT
