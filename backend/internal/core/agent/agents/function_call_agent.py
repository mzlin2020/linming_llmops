"""FunctionCallAgent：依赖模型原生 tool_call 的智能体（LangGraph 1.x）。

图结构（去掉本轮用不到的 preset_operation / 长期记忆节点）：

    START → llm ──(有 tool_calls)──→ tools → llm（循环）
                └──(无 tool_calls)──→ END

流式策略：在 _llm_node 内**显式** llm.stream()，把回答 token 增量通过 get_stream_writer
以 custom 事件 {"delta": ...} 推出去——不依赖 LangGraph messages 模式的隐式 token 捕获，
对真实 ChatOpenAI 与测试用的假模型表现一致。工具调用/结果由外层 runtime 在 updates 模式识别。
"""
from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import START, StateGraph
from langgraph.prebuilt import tools_condition

try:  # get_stream_writer 在节点内推 custom 事件；invoke（非流式）场景下可能取不到，容错为 None
    from langgraph.config import get_stream_writer
except Exception:  # pragma: no cover
    get_stream_writer = None  # type: ignore[assignment]

from ..entities.agent_entity import AgentState
from .base_agent import BaseAgent


class FunctionCallAgent(BaseAgent):
    def build_graph(self) -> Any:
        graph = StateGraph(AgentState)
        graph.add_node("llm", self._llm_node)
        graph.add_node("tools", self._tools_node)
        graph.add_edge(START, "llm")
        # tools_condition：末条消息有 tool_calls → "tools"，否则 → END
        graph.add_conditional_edges("llm", tools_condition)
        graph.add_edge("tools", "llm")
        return graph.compile()

    # ---------- nodes ----------

    def _llm_node(self, state: AgentState) -> dict:
        cfg = self.agent_config
        llm = self.llm
        # 到达最大迭代轮数的最后一次调用不再绑工具，逼模型给出最终文本答案（→END），防死循环
        bind = (
            cfg.tool_call_supported
            and bool(cfg.tools)
            and state["iteration_count"] < cfg.max_iteration_count
        )
        if bind:
            llm = llm.bind_tools(cfg.tools)

        writer = _stream_writer()
        gathered: Any = None
        for chunk in llm.stream(state["messages"]):
            gathered = chunk if gathered is None else gathered + chunk
            content = getattr(chunk, "content", "")
            if writer is not None and isinstance(content, str) and content:
                writer({"delta": content})
        if gathered is None:
            gathered = AIMessage(content="")
        return {
            "messages": [gathered],
            "iteration_count": state["iteration_count"] + 1,
        }

    def _tools_node(self, state: AgentState) -> dict:
        tools_by_name = {t.name: t for t in self.agent_config.tools}
        last = state["messages"][-1]
        out: list[ToolMessage] = []
        for tc in getattr(last, "tool_calls", None) or []:
            tool = tools_by_name.get(tc["name"])
            if tool is None:
                result: Any = f"工具不存在: {tc['name']}"
            else:
                try:
                    result = tool.invoke(tc["args"])
                except Exception as e:  # 工具异常吞成可观测文本，不让整轮对话崩
                    result = f"工具执行出错: {e}"
            content = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
            out.append(ToolMessage(tool_call_id=tc["id"], name=tc["name"], content=content))
        return {"messages": out}


def _stream_writer():
    if get_stream_writer is None:
        return None
    try:
        return get_stream_writer()
    except Exception:  # 非流式（graph.invoke）上下文下没有 writer
        return None
