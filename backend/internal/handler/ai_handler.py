"""AI 辅助生成接口：优化人设 / 生成开场问题 / 生成后续追问。

均为同步返回（{code,message,data}），与编排页的 ✨ 按钮配合：前端转圈等待结果。
"""
from dataclasses import dataclass

from flask import request
from flask_login import current_user
from injector import inject
from pydantic import ValidationError

from internal.exception import ValidateErrorException
from internal.lib.helper import first_validation_error as _first_error
from internal.middleware import RequireLogin
from internal.schema.ai_schema import (
    OptimizePromptReq,
    SuggestOpeningQuestionsReq,
    SuggestQuestionsReq,
)
from internal.service import AIService
from pkg.response import success


@inject
@dataclass
class AIHandler:
    ai_service: AIService

    @RequireLogin
    def optimize_preset_prompt(self):
        """POST /ai/optimize-preset-prompt —— 优化人设提示词，返回 {prompt}。"""
        try:
            req = OptimizePromptReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        return success({"prompt": self.ai_service.optimize_preset_prompt(req.prompt)})

    @RequireLogin
    def suggest_opening_questions(self):
        """POST /ai/suggested-opening-questions —— 据人设生成开场问题，返回 string[]。"""
        try:
            req = SuggestOpeningQuestionsReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        return success(self.ai_service.suggest_opening_questions(req.prompt))

    @RequireLogin
    def suggest_questions(self):
        """POST /ai/suggested-questions —— 据一轮问答生成 follow-up，返回 string[]。"""
        try:
            req = SuggestQuestionsReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        return success(self.ai_service.suggest_questions_from_message(current_user, req.message_id))
