"""chat 链路共享的小工具：SSE 帧编码 / LangChain 消息构建 / provider·model 解析。

ChatService（多会话）与 AssistantAgentService（单会话辅助 Agent）都用这几个，抽出来避免复制。
"""
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from internal.core.language_model.defaults import resolve_default_provider_model
from internal.entity import QueueEvent


def sse(event: QueueEvent, payload: dict) -> str:
    """编码一帧 SSE：`event: <name>\\ndata: <JSON>\\n\\n`（无裸 data / [DONE]）。"""
    return f"event: {event.value}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@dataclass
class HistoryTurn:
    """历史一条：role + 文本 + （仅 user 轮）该轮附件。conversation_service.history_for_llm 产出。"""
    role: str
    content: str
    image_urls: list[str] = field(default_factory=list)
    file_infos: list[dict] = field(default_factory=list)


def _build_human(
    text: str, image_urls: list[str], file_infos: list[dict], supports_vision: bool,
) -> HumanMessage:
    """构造一条 user 消息：文档抽取文本拼进正文（任何模型可用）；
    图片在 vision 模型下构造 OpenAI 协议的 image_url content parts，
    非 vision 模型（历史中途切换的场景）降级为 [图片] 占位文本，不阻断。"""
    full_text = text or ""
    for fi in file_infos or []:
        body = (fi.get("text") or "").strip()
        if body:
            name = fi.get("name") or "文件"
            full_text += f"\n\n用户上传了文件《{name}》，内容如下：\n{body}"
    imgs = image_urls or []
    if imgs and supports_vision:
        parts: list[dict] = [{"type": "text", "text": full_text}]
        parts.extend({"type": "image_url", "image_url": {"url": u}} for u in imgs)
        return HumanMessage(content=parts)
    if imgs:
        full_text += "\n" + "\n".join("[图片]" for _ in imgs)
    return HumanMessage(content=full_text)


def build_lc_messages(
    system_prompt: str,
    history: list[HistoryTurn],
    user_query: str,
    *,
    image_urls: Optional[list[str]] = None,
    file_infos: Optional[list[dict]] = None,
    supports_vision: bool = False,
) -> list[BaseMessage]:
    """组装 LLM 输入。history 为 HistoryTurn 列表（带附件，历史轮按相同规则重建多模态）；
    命名/摘要等纯文本场景传 []。当前轮附件经 kwargs 传入。"""
    msgs: list[BaseMessage] = []
    if system_prompt:
        msgs.append(SystemMessage(content=system_prompt))
    for turn in history:
        if turn.role == "user":
            msgs.append(_build_human(turn.content, turn.image_urls, turn.file_infos, supports_vision))
        elif turn.role == "assistant":
            msgs.append(AIMessage(content=turn.content))
        elif turn.role == "system":
            msgs.append(SystemMessage(content=turn.content))
    msgs.append(_build_human(user_query, image_urls or [], file_infos or [], supports_vision))
    return msgs


def compose_system_prompt(config, conv) -> str:
    """组装系统提示词：人设 preset_prompt + （开启长期记忆且有摘要时）注入会话长期记忆。

    裸 LLM 与 Agent 两条路都在 build_lc_messages 之前取 system_prompt，故只需在此一处注入即可同时覆盖。
    （注：全局辅助 Agent assistant_agent_service 有意不走这里——它不是长期记忆场景。）
    config 为草稿/已发布配置行（带 preset_prompt / long_term_memory），conv 为当前会话（带 summary）。"""
    base = (getattr(config, "preset_prompt", "") or "")
    summary = (getattr(conv, "summary", "") or "").strip()
    if ltm_enabled(config) and summary:
        return f"{base}\n\n## 长期记忆\n以下是你与该用户过往对话的长期记忆，回答时可参考：\n{summary}".strip()
    return base


def extract_text(resp) -> str:
    """从 LLM 返回对象取文本内容；content 非字符串（如多模态 list）时回退到 str(resp)。
    抽出来统一裸 LLM / 摘要 / AI 辅助等各处对 `.content` 的取值与兜底。"""
    content = getattr(resp, "content", None)
    if isinstance(content, str):
        return content
    return str(resp) if resp is not None else ""


def usage_of(msg) -> tuple[int, int]:
    """从 LLM 响应 / 流式聚合块取 (input_tokens, output_tokens)，缺失或异常一律回 (0, 0)。

    OpenAI 兼容模型（实例化时 stream_usage=True）：invoke 的 AIMessage、stream 聚合后的
    AIMessageChunk 都带 `usage_metadata = {"input_tokens", "output_tokens", "total_tokens"}`。
    fake_llm 等不带该属性的实现自然回 (0, 0)，不报错。"""
    try:
        um = getattr(msg, "usage_metadata", None)
        if not um:
            return 0, 0
        return int(um.get("input_tokens") or 0), int(um.get("output_tokens") or 0)
    except Exception:
        return 0, 0


def ltm_enabled(config) -> bool:
    """该配置是否开启长期记忆。与 compose_system_prompt 读同一字段，保持判定同源。"""
    return bool((getattr(config, "long_term_memory", None) or {}).get("enable"))


def resolve_provider_model(config) -> tuple[str, str]:
    """优先配置行（草稿 / 已发布配置）的 model_config 里的 provider/model；fallback 环境变量默认值。
    入参是带 `.model_config` 属性的配置对象（AppConfigVersion / AppConfig），而非 App 本身——
    三表拆分后 model_config 已迁出 ai_app。"""
    cfg: dict[str, Any] = getattr(config, "model_config", None) or {}
    return resolve_default_provider_model(cfg)
