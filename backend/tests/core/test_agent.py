"""FunctionCallAgent 回合 + ToolResolver 解析（纯本机：脚本化假模型 + 内置 time 工具，无 DB/LLM/torch）。

Agent 走 LangGraph custom 流：节点内显式 .stream() + writer 推 token，不依赖真实 BaseChatModel，
故用 duck-typed _ScriptedToolLLM 即可驱动整张图。api_tool（_resolve_api）走 DB，交 CI，不在此测。
"""
import re

from langchain_core.messages import AIMessageChunk, HumanMessage, ToolMessage

from internal.core.agent import AgentConfig, FunctionCallAgent, ToolResolver
from internal.core.tools.api_tools.providers import ApiProviderManager
from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.core.tools.builtin_tools.providers.time.current_time import current_time


class _ScriptedToolLLM:
    """duck-typed 假 ChatModel：按脚本顺序产出 AIMessageChunk（先工具调用，再最终文本）。"""

    def __init__(self, script):
        self._script = list(script)
        self._idx = 0
        self.bind_calls = []

    def bind_tools(self, tools, **kwargs):
        self.bind_calls.append(tools)
        return self

    def _next(self):
        chunk = self._script[min(self._idx, len(self._script) - 1)]
        self._idx += 1
        return chunk

    def stream(self, messages, *args, **kwargs):
        yield self._next()

    def invoke(self, messages, *args, **kwargs):
        from langchain_core.messages import AIMessage
        chunk = self._next()
        return AIMessage(content=chunk.content, tool_calls=list(getattr(chunk, "tool_calls", []) or []))


def _tool_call_then_text():
    return [
        AIMessageChunk(content="", tool_calls=[
            {"name": "current_time", "args": {}, "id": "call_1", "type": "tool_call"},
        ]),
        AIMessageChunk(content="现在时间已获取。"),
    ]


def _agent(script, **cfg):
    config = AgentConfig(tools=[current_time()], tool_call_supported=True, **cfg)
    return FunctionCallAgent(llm=_ScriptedToolLLM(script), agent_config=config)


class TestFunctionCallAgent:
    def test_tool_round_then_final_answer(self):
        agent = _agent(_tool_call_then_text())
        result = agent.graph.invoke({"messages": [HumanMessage(content="现在几点")], "iteration_count": 0})

        # 工具确实被执行：消息流里有 current_time 的 ToolMessage（内容为时间串）
        tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert len(tool_msgs) == 1 and tool_msgs[0].name == "current_time"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", tool_msgs[0].content)
        # 末条消息是模型最终文本答案
        assert result["messages"][-1].content == "现在时间已获取。"

    def test_custom_stream_emits_token_deltas(self):
        agent = _agent(_tool_call_then_text())
        deltas = [
            ev["delta"]
            for ev in agent.graph.stream(
                {"messages": [HumanMessage(content="现在几点")], "iteration_count": 0},
                stream_mode="custom",
            )
            if isinstance(ev, dict) and "delta" in ev
        ]
        # 工具轮 content="" 不推 delta；最终文本轮推出答案
        assert "".join(deltas) == "现在时间已获取。"

    def test_max_iteration_gate_unbinds_tools_on_last_round(self):
        # 脚本连开两轮工具再给文本；max=2 → 仅前两次 llm 调用绑工具，第三次（iteration==max）不绑
        script = [
            AIMessageChunk(content="", tool_calls=[{"name": "current_time", "args": {}, "id": "c1", "type": "tool_call"}]),
            AIMessageChunk(content="", tool_calls=[{"name": "current_time", "args": {}, "id": "c2", "type": "tool_call"}]),
            AIMessageChunk(content="完成。"),
        ]
        agent = _agent(script, max_iteration_count=2)
        result = agent.graph.invoke({"messages": [HumanMessage(content="x")], "iteration_count": 0})
        assert agent.llm.bind_calls and len(agent.llm.bind_calls) == 2  # 第三次未绑工具
        assert result["messages"][-1].content == "完成。"


class TestToolResolver:
    def _resolver(self):
        return ToolResolver(
            builtin_provider_manager=BuiltinProviderManager(),
            api_provider_manager=ApiProviderManager(),
        )

    def _builtin_cfg(self):
        return [{"type": "builtin_tool", "provider": {"name": "time"}, "tool": {"name": "current_time", "params": {}}}]

    def test_resolve_builtin_time(self):
        tools = self._resolver().resolve(self._builtin_cfg())
        assert len(tools) == 1 and tools[0].name == "current_time"

    def test_unknown_builtin_skipped_not_raised(self):
        cfg = [{"type": "builtin_tool", "provider": {"name": "ghost"}, "tool": {"name": "nope"}}]
        assert self._resolver().resolve(cfg) == []

    def test_admin_only_gate(self, monkeypatch):
        # 现网内置工具均非 admin_only（image_generation 在 v1.1 改为对所有人开放），临时把 time 标成 admin_only 验证闸门双分支
        resolver = self._resolver()
        provider = resolver.builtin_provider_manager.get_provider("time")
        monkeypatch.setattr(provider.provider_entity, "admin_only", True)
        assert resolver.resolve(self._builtin_cfg(), is_admin=False) == []          # 非超管跳过
        granted = resolver.resolve(self._builtin_cfg(), is_admin=True)
        assert len(granted) == 1 and granted[0].name == "current_time"              # 超管放行
