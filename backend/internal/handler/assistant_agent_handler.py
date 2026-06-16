from dataclasses import dataclass

from flask import request
from flask_login import current_user
from injector import inject
from pydantic import ValidationError

from internal.exception import ValidateErrorException
from internal.lib.helper import first_validation_error as _first_error
from internal.middleware import RequireLogin
from internal.schema.assistant_agent_schema import AssistantAgentChatReq
from internal.schema.conversation_schema import GetMessagesWithPageReq
from internal.service import AssistantAgentService
from pkg.response import compact_generate_response, success, success_message


@inject
@dataclass
class AssistantAgentHandler:
    """辅助 Agent：单会话聊天（URL 形状 /assistant-agent/*）。"""
    assistant_agent_service: AssistantAgentService

    def _parse_chat_req(self) -> AssistantAgentChatReq:
        try:
            return AssistantAgentChatReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))

    @RequireLogin
    def chat(self):
        """POST /assistant-agent/chat —— SSE 流式聊天。"""
        req = self._parse_chat_req()
        gen = self.assistant_agent_service.chat(current_user, req)
        return compact_generate_response(gen)

    @RequireLogin
    def complete(self):
        """POST /assistant-agent/chat/complete —— 同步兜底（非 SSE）。"""
        req = self._parse_chat_req()
        return success(self.assistant_agent_service.complete(current_user, req))

    @RequireLogin
    def messages(self):
        """GET /assistant-agent/messages —— 分页拉当前会话历史。"""
        try:
            req = GetMessagesWithPageReq.model_validate(request.args.to_dict(flat=True))
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        page = self.assistant_agent_service.list_messages(current_user, req)
        return success(page.model_dump(mode="json"))

    @RequireLogin
    def delete_conversation(self):
        """POST /assistant-agent/delete-conversation —— 清空（软删当前会话）。"""
        self.assistant_agent_service.clear_conversation(current_user)
        return success_message("ok")

    @RequireLogin
    def stop(self, task_id: str):
        """POST /assistant-agent/chat/<task_id>/stop —— 中断该 task 的 Agent 流式生成。"""
        self.assistant_agent_service.stop(current_user, task_id)
        return success_message("ok")
