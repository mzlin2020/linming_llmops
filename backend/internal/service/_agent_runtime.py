"""Agent 运行时的流式 / 同步内核，被 ChatService 与 AssistantAgentService 共用。

与 _chat_common（裸 LLM 流）并列：当 app 配置挂了工具且模型支持 tool_call 时，chat 走这里——
构 FunctionCallAgent 图，以 stream_mode=["custom","updates"] 同时拿：
  ① 回答 token 增量（custom，{"delta": ...}）              → event: message
  ② 工具调用决策 / 工具执行结果（updates）                  → event: agent_thought / agent_action
翻译成既有 SSE 协议；finally 里 finalize_round + 落 ai_message_agent_thought。

真·停止：task_id 登记归属到 redis，generator 每帧查 stopped flag，可秒级中断。
DB 写一律在 stream 跑完后（finally）单次提交，绝不与 yield 交错（stream_with_context 下 session 一致性）。
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Generator, Optional

from langchain_core.messages import AIMessage, ToolMessage

from internal.core.agent import AgentConfig, FunctionCallAgent
from internal.core.agent.entities.agent_entity import DEFAULT_MAX_ITERATION_COUNT
from internal.entity import MessageStatus, QueueEvent
from internal.extension.database_extension import db
from internal.extension.redis_extension import redis_client
from internal.model import MessageAgentThought
from internal.service._chat_common import extract_text, sse as _sse, usage_of
from internal.service.conversation_service import ConversationService

_BELONG_PREFIX = "agent_task_belong:"
_STOPPED_PREFIX = "agent_task_stopped:"
_BELONG_TTL = 1800
_STOPPED_TTL = 600
# 停止 flag 的查询节流：每帧都查会变成「一 token 一次 redis GET」，按时间间隔查即可保持秒级中断
_STOP_CHECK_INTERVAL = 0.25


def max_iteration_count() -> int:
    try:
        return int(os.getenv("AGENT_MAX_ITERATIONS") or DEFAULT_MAX_ITERATION_COUNT)
    except (TypeError, ValueError):
        return DEFAULT_MAX_ITERATION_COUNT


# ---------------- redis：task 归属 / 停止 ----------------

def register_task(task_id: str, user_id: int) -> None:
    redis_client.set(f"{_BELONG_PREFIX}{task_id}", f"account-{user_id}", ex=_BELONG_TTL)


def is_stopped(task_id: str) -> bool:
    return redis_client.get(f"{_STOPPED_PREFIX}{task_id}") is not None


def clear_task(task_id: str) -> None:
    redis_client.delete(f"{_BELONG_PREFIX}{task_id}", f"{_STOPPED_PREFIX}{task_id}")


def request_stop(task_id: str, user_id: int) -> bool:
    """置停止 flag。task_id 必须属于该 user（防跨用户停止）。不存在 / 越权 / 已结束均静默返回 False。"""
    belong = redis_client.get(f"{_BELONG_PREFIX}{task_id}")
    if not belong:
        return False
    val = belong.decode() if isinstance(belong, (bytes, bytearray)) else str(belong)
    if val != f"account-{user_id}":
        return False
    redis_client.set(f"{_STOPPED_PREFIX}{task_id}", b"1", ex=_STOPPED_TTL)
    return True


# ---------------- agent_thought 派生 / 落库 ----------------

def message_to_thought(m: Any, position: int, args_by_id: dict) -> Optional[dict]:
    """把单条 LangChain 消息映射成一行 agent_thought / agent_action（非工具相关消息返回 None）。
    带 tool_calls 的 AIMessage → agent_thought；ToolMessage → agent_action（tool_input 回填自前序 tool_calls）。
    args_by_id 在多次调用间累积 tool_call 入参，供后续 ToolMessage 按 tool_call_id 回填。
    流式与同步两条路径共用此映射，避免重复走一遍消息列表。"""
    if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
        for tc in m.tool_calls:
            args_by_id[tc.get("id")] = tc.get("args", {})
        return {
            "position": position, "event": QueueEvent.AGENT_THOUGHT.value,
            "thought": _dumps(m.tool_calls), "tool": "", "tool_input": {}, "observation": "",
        }
    if isinstance(m, ToolMessage):
        content = m.content if isinstance(m.content, str) else _dumps(m.content)
        return {
            "position": position, "event": QueueEvent.AGENT_ACTION.value, "thought": "",
            "tool": m.name or "", "tool_input": args_by_id.get(m.tool_call_id, {}), "observation": content,
        }
    return None


def build_thoughts(messages: list[Any]) -> list[dict]:
    """同步路径：从完整消息列表派生 agent_thought 行（输入的 System/Human、历史纯文本 AIMessage 自然跳过）。"""
    thoughts: list[dict] = []
    args_by_id: dict[Any, Any] = {}
    for m in messages:
        t = message_to_thought(m, len(thoughts) + 1, args_by_id)
        if t is not None:
            thoughts.append(t)
    return thoughts


def persist_thoughts(
    *, message_id: int, conversation_id: int, app_id: int,
    user_id: int, invoke_from: str, thoughts: list[dict],
) -> None:
    if not thoughts:
        return
    with db.auto_commit():
        for t in thoughts:
            db.session.add(MessageAgentThought(
                app_id=app_id,
                conversation_id=conversation_id,
                message_id=message_id,
                invoke_from=invoke_from,
                created_by=user_id,
                position=t["position"],
                event=t["event"],
                thought=t.get("thought", ""),
                observation=t.get("observation", ""),
                tool=t.get("tool", ""),
                tool_input=t.get("tool_input") or {},
            ))


def _dumps(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return str(obj)


def _build_agent(llm: Any, tools: list, tool_call_supported: bool) -> FunctionCallAgent:
    return FunctionCallAgent(
        llm,
        AgentConfig(
            tools=tools,
            tool_call_supported=tool_call_supported,
            max_iteration_count=max_iteration_count(),
        ),
    )


def _init_state(lc_messages: list) -> dict:
    return {"messages": lc_messages, "iteration_count": 0}


# ---------------- 流式 ----------------

def run_agent_stream(
    *,
    conversation_service: ConversationService,
    llm: Any,
    tools: list,
    tool_call_supported: bool,
    lc_messages: list,
    conv_id: int,
    msg_id: int,
    app_id: int,
    user_id: int,
    invoke_from: str,
    provider: Optional[str],
    model_name: Optional[str],
    task_id: str,
    long_term_memory_enabled: bool = False,
) -> Generator[str, None, None]:
    """SSE 事件序列：ping → (agent_thought → agent_action)* → message×N → agent_end。
    异常分支插 error；用户停止插 stop。两者都仍跑 finally（finalize_round + 落 thought）。"""
    yield _sse(QueueEvent.PING, {"task_id": task_id})
    register_task(task_id, user_id)

    agent = _build_agent(llm, tools, tool_call_supported)

    answer_parts: list[str] = []
    thoughts: list[dict] = []
    args_by_id: dict[Any, Any] = {}
    in_tok = 0  # 跨多轮 LLM 调用累加 usage（每次 _llm_node 产出一条带 usage 的 AIMessage）
    out_tok = 0
    status = MessageStatus.NORMAL.value
    err = ""
    started = time.time()
    last_stop_check = 0.0
    try:
        for mode, data in agent.graph.stream(_init_state(lc_messages), stream_mode=["custom", "updates"]):
            now = time.time()
            if now - last_stop_check >= _STOP_CHECK_INTERVAL:
                last_stop_check = now
                if is_stopped(task_id):
                    status = MessageStatus.STOP.value
                    yield _sse(QueueEvent.STOP, {"conversation_id": conv_id, "message_id": msg_id})
                    break
            if mode == "custom":
                delta = data.get("delta") if isinstance(data, dict) else None
                if delta:
                    answer_parts.append(delta)
                    yield _sse(QueueEvent.MESSAGE, {
                        "conversation_id": conv_id, "message_id": msg_id, "delta": delta,
                    })
            elif mode == "updates":
                for _node, upd in (data or {}).items():
                    for m in (upd or {}).get("messages", []) or []:
                        if isinstance(m, AIMessage):
                            i, o = usage_of(m)
                            in_tok += i
                            out_tok += o
                        t = message_to_thought(m, len(thoughts) + 1, args_by_id)
                        if t is None:
                            continue
                        thoughts.append(t)
                        if t["event"] == QueueEvent.AGENT_THOUGHT.value:
                            yield _sse(QueueEvent.AGENT_THOUGHT, {
                                "conversation_id": conv_id, "message_id": msg_id,
                                "position": t["position"], "tool_calls": m.tool_calls,
                            })
                        else:
                            yield _sse(QueueEvent.AGENT_ACTION, {
                                "conversation_id": conv_id, "message_id": msg_id,
                                "position": t["position"], "tool": t["tool"], "observation": t["observation"],
                            })
    except Exception as e:
        status = MessageStatus.ERROR.value
        err = str(e)[:500]
        yield _sse(QueueEvent.ERROR, {"message": err, "message_id": msg_id})
    finally:
        full = "".join(answer_parts)
        latency = round(time.time() - started, 3)
        msg_row = conversation_service.finalize_round(
            msg_id, answer=full, provider=provider, model_name=model_name,
            latency=latency, status=status, error=err,
            input_token_count=in_tok, output_token_count=out_tok,
        )
        _safe_persist(
            message_id=msg_id, conversation_id=conv_id, app_id=app_id,
            user_id=user_id, invoke_from=invoke_from, thoughts=thoughts,
        )
        # 对话后统一收尾（命名 + 长期记忆）：投递 Celery 异步，agent_end 不再等它（与裸 LLM 路一致）
        conversation_service.enqueue_after_round(
            msg_id, provider=provider, model=model_name,
            long_term_memory_enabled=long_term_memory_enabled,
        )
        clear_task(task_id)
        yield _sse(QueueEvent.AGENT_END, {
            "conversation_id": conv_id, "message_id": msg_id,
            "total_token_count": int(msg_row.total_token_count or 0),
            "latency": latency, "status": status,
        })


# ---------------- 同步 ----------------

def run_agent_complete(
    *,
    conversation_service: ConversationService,
    llm: Any,
    tools: list,
    tool_call_supported: bool,
    lc_messages: list,
    conv_id: int,
    msg_id: int,
    app_id: int,
    user_id: int,
    invoke_from: str,
    provider: Optional[str],
    model_name: Optional[str],
    query: str,
    long_term_memory_enabled: bool = False,
) -> dict:
    agent = _build_agent(llm, tools, tool_call_supported)
    started = time.time()
    status = MessageStatus.NORMAL.value
    err = ""
    answer = ""
    messages_out: list[Any] = []
    in_tok = 0
    out_tok = 0
    try:
        result = agent.graph.invoke(_init_state(lc_messages))
        messages_out = result.get("messages", []) or []
        for m in messages_out:  # 累加各轮 LLM 调用的 usage
            if isinstance(m, AIMessage):
                i, o = usage_of(m)
                in_tok += i
                out_tok += o
        for m in reversed(messages_out):  # 末条无 tool_calls 的 AIMessage = 最终答案
            if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None):
                content = m.content
                answer = content if isinstance(content, str) else _dumps(content)
                break
    except Exception as e:
        status = MessageStatus.ERROR.value
        err = str(e)[:500]
    latency = round(time.time() - started, 3)
    msg_row = conversation_service.finalize_round(
        msg_id, answer=answer, provider=provider, model_name=model_name,
        latency=latency, status=status, error=err,
        input_token_count=in_tok, output_token_count=out_tok,
    )
    _safe_persist(
        message_id=msg_id, conversation_id=conv_id, app_id=app_id,
        user_id=user_id, invoke_from=invoke_from, thoughts=build_thoughts(messages_out),
    )
    # 收尾投递 Celery 异步（命名 + 长期记忆），不阻塞同步响应返回
    conversation_service.enqueue_after_round(
        msg_id, provider=provider, model=model_name,
        long_term_memory_enabled=long_term_memory_enabled,
    )
    return {
        "conversation_id": conv_id, "message_id": msg_id, "query": query,
        "answer": answer, "latency": latency, "provider": provider,
        "model_name": model_name, "status": status, "error": err,
        "total_token_count": int(msg_row.total_token_count or 0),
    }


# ---------------- 裸 LLM（无工具）：流式 / 同步 ----------------
# 与上面的 agent 内核并列：模型不支持 tool_call 或未配工具时，chat 走这两个。
# ChatService 与 AssistantAgentService 共用，避免在两个 service 里各抄一份流式/同步收尾逻辑。

def run_llm_stream(
    *,
    conversation_service: ConversationService,
    llm: Any,
    lc_messages: list,
    conv_id: int,
    msg_id: int,
    provider: Optional[str],
    model_name: Optional[str],
    task_id: str,
    long_term_memory_enabled: bool = False,
) -> Generator[str, None, None]:
    """SSE 事件序列：ping → message×N → agent_end，异常分支插 error。
    task_id 仅用于 ping 帧回传——裸流不登记 redis 任务，故 stop 对它自然 no-op。"""
    yield _sse(QueueEvent.PING, {"task_id": task_id})
    parts: list[str] = []
    gathered = None  # 聚合流式块以取末帧 usage（stream_usage=True）
    status = MessageStatus.NORMAL.value
    err = ""
    started = time.time()
    try:
        for chunk in llm.stream(lc_messages):
            try:  # 聚合块取末帧 usage；块类型不支持相加时退化为保留末块（usage 退化为 0）
                gathered = chunk if gathered is None else gathered + chunk
            except Exception:
                gathered = chunk
            delta = getattr(chunk, "content", None)
            if not isinstance(delta, str):
                delta = str(chunk) if chunk is not None else ""
            if delta:
                parts.append(delta)
                yield _sse(QueueEvent.MESSAGE, {
                    "conversation_id": conv_id, "message_id": msg_id, "delta": delta,
                })
    except Exception as e:
        status = MessageStatus.ERROR.value
        err = str(e)[:500]
        yield _sse(QueueEvent.ERROR, {"message": err, "message_id": msg_id})
    finally:
        full = "".join(parts)
        latency = round(time.time() - started, 3)
        in_tok, out_tok = usage_of(gathered)
        msg_row = conversation_service.finalize_round(
            msg_id, answer=full, provider=provider, model_name=model_name,
            latency=latency, status=status, error=err,
            input_token_count=in_tok, output_token_count=out_tok,
        )
        # 对话后统一收尾（命名 + 长期记忆）：投递 Celery 异步，agent_end 不再等它（与 agent 路一致）
        conversation_service.enqueue_after_round(
            msg_id, provider=provider, model=model_name,
            long_term_memory_enabled=long_term_memory_enabled,
        )
        yield _sse(QueueEvent.AGENT_END, {
            "conversation_id": conv_id, "message_id": msg_id,
            "total_token_count": int(msg_row.total_token_count or 0),
            "latency": latency, "status": status,
        })


def run_llm_complete(
    *,
    conversation_service: ConversationService,
    llm: Any,
    lc_messages: list,
    conv_id: int,
    msg_id: int,
    provider: Optional[str],
    model_name: Optional[str],
    query: str,
    long_term_memory_enabled: bool = False,
) -> dict:
    """同步版：一次 llm.invoke，写一条 ai_message，返回结果 dict。"""
    started = time.time()
    status = MessageStatus.NORMAL.value
    err = ""
    answer = ""
    in_tok, out_tok = 0, 0
    try:
        response = llm.invoke(lc_messages)
        answer = extract_text(response)
        in_tok, out_tok = usage_of(response)
    except Exception as e:
        status = MessageStatus.ERROR.value
        err = str(e)[:500]
    latency = round(time.time() - started, 3)
    msg_row = conversation_service.finalize_round(
        msg_id, answer=answer, provider=provider, model_name=model_name,
        latency=latency, status=status, error=err,
        input_token_count=in_tok, output_token_count=out_tok,
    )
    # 收尾投递 Celery 异步（命名 + 长期记忆），不阻塞同步响应返回
    conversation_service.enqueue_after_round(
        msg_id, provider=provider, model=model_name,
        long_term_memory_enabled=long_term_memory_enabled,
    )
    return {
        "conversation_id": conv_id, "message_id": msg_id, "query": query,
        "answer": answer, "latency": latency, "provider": provider,
        "model_name": model_name, "status": status, "error": err,
        "total_token_count": int(msg_row.total_token_count or 0),
    }


def _safe_persist(**kwargs: Any) -> None:
    try:
        persist_thoughts(**kwargs)
    except Exception:  # 落库失败不影响已经回写的 answer/latency 与 SSE 收尾
        db.session.rollback()
