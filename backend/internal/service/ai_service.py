"""AI 辅助生成：优化人设 / 生成开场问题 / 生成后续追问。

三者都用默认 LLM 做一次性同步 invoke（不流式），复用 _chat_common.build_lc_messages 组装消息。
建议问题统一让模型只返回 JSON 字符串数组，再由 _parse_questions 容错解析——不依赖
with_structured_output（兼容各 OpenAI 兼容模型，也能用返回字符串的 fake_llm 直接单测）。
"""
import json
import re
from dataclasses import dataclass
from typing import Any

from injector import inject

from internal.core.language_model.language_model_manager import LanguageModelManager
from internal.entity import (
    OPENING_QUESTIONS_TEMPLATE,
    OPTIMIZE_PROMPT_TEMPLATE,
    SUGGESTED_QUESTIONS_TEMPLATE,
)
from internal.exception import ForbiddenException, NotFoundException
from internal.extension.database_extension import db
from internal.model import Account, Message
from internal.service._chat_common import build_lc_messages, extract_text

_MAX_QUESTIONS = 3


@inject
@dataclass
class AIService:
    llm_manager: LanguageModelManager

    def optimize_preset_prompt(self, prompt: str) -> str:
        """把用户填写的人设提示词优化重写，返回整段优化后文本。"""
        messages = build_lc_messages(OPTIMIZE_PROMPT_TEMPLATE, [], prompt)
        return self._invoke_text(messages)

    def suggest_opening_questions(self, prompt: str) -> list[str]:
        """根据人设生成最多 3 条开场建议问题。"""
        human = prompt.strip() or "（用户暂未填写人设，请生成几个通用的、适合向 AI 助手提出的问题）"
        messages = build_lc_messages(OPENING_QUESTIONS_TEMPLATE, [], human)
        return self._parse_questions(self._invoke_text(messages))

    def suggest_questions_from_message(self, user: Account, message_id: int) -> list[str]:
        """根据某条消息（一轮问答）生成最多 3 条 follow-up 建议问题。"""
        msg = db.session.get(Message, message_id)
        if msg is None or msg.is_deleted:
            raise NotFoundException("消息不存在")
        if msg.created_by != user.id and not user.is_admin:
            raise ForbiddenException("无权访问该消息")
        histories = f"Human: {msg.query}\nAI: {msg.answer or ''}"
        messages = build_lc_messages(SUGGESTED_QUESTIONS_TEMPLATE, [], histories)
        return self._parse_questions(self._invoke_text(messages))

    # ---------- internal ----------

    def _invoke_text(self, messages: list) -> str:
        return extract_text(self.llm_manager.get_default().invoke(messages))

    @staticmethod
    def _parse_questions(text: str) -> list[str]:
        """从模型输出里抽取首个 JSON 数组并解析成字符串列表；失败回 []。最多 3 条。"""
        if not isinstance(text, str):
            return []
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return []
        try:
            data: Any = json.loads(match.group(0))
        except (ValueError, TypeError):
            return []
        if not isinstance(data, list):
            return []
        questions = [str(q).strip() for q in data if isinstance(q, (str, int, float)) and str(q).strip()]
        return questions[:_MAX_QUESTIONS]
