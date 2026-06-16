"""Agent 基类：持有 llm + AgentConfig，子类 build_graph() 编译出可流式的图。

刻意保持极薄——不背旧式 0.x 的 Serializable / Runnable / AgentQueueManager 那套。
流式调度与事件翻译统一交给 service 层的 _agent_runtime（前台 generator 直接 yield）。
"""
from __future__ import annotations

from typing import Any

from ..entities.agent_entity import AgentConfig


class BaseAgent:
    def __init__(self, llm: Any, agent_config: AgentConfig) -> None:
        self.llm = llm
        self.agent_config = agent_config
        self.graph = self.build_graph()

    def build_graph(self) -> Any:
        raise NotImplementedError
