"""ConversationHandler：会话列表/详情/改名/置顶/删除 + 消息分页/删除（按 user 归属隔离）。全部要求登录。"""
from dataclasses import dataclass

from flask import request
from flask_login import current_user
from injector import inject
from pydantic import ValidationError

from internal.exception import ValidateErrorException
from internal.lib.helper import first_validation_error as _first_error
from internal.middleware import RequireLogin
from internal.schema.conversation_schema import (
    ConversationIsPinnedReq,
    ConversationItem,
    ConversationRenameReq,
    GetMessagesWithPageReq,
)
from internal.service import ConversationService
from pkg.response import success, success_message


@inject
@dataclass
class ConversationHandler:
    conversation_service: ConversationService

    @RequireLogin
    def list_conversations(self):
        app_id_raw = request.args.get("app_id")
        try:
            app_id = int(app_id_raw) if app_id_raw is not None else None
        except ValueError:
            raise ValidateErrorException(message="app_id 必须是整数")
        try:
            limit = int(request.args.get("limit", 50))
        except ValueError:
            raise ValidateErrorException(message="limit 必须是整数")
        limit = max(1, min(limit, 200))

        items = self.conversation_service.list_by_user(current_user, app_id=app_id, limit=limit)
        return success([ConversationItem.model_validate(c).model_dump(mode="json") for c in items])

    @RequireLogin
    def get_conversation(self, conversation_id: int):
        conv = self.conversation_service.get(current_user, conversation_id)
        return success(ConversationItem.model_validate(conv).model_dump(mode="json"))

    @RequireLogin
    def list_messages(self, conversation_id: int):
        """GET /conversations/<id>/messages —— 分页返回该会话的消息（PageModel）。"""
        try:
            req = GetMessagesWithPageReq.model_validate(request.args.to_dict(flat=True))
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        page = self.conversation_service.list_messages_with_page(current_user, conversation_id, req)
        return success(page.model_dump(mode="json"))

    @RequireLogin
    def delete_conversation(self, conversation_id: int):
        self.conversation_service.delete(current_user, conversation_id)
        return success_message("已删除")

    @RequireLogin
    def delete_message(self, conversation_id: int, message_id: int):
        self.conversation_service.delete_message(current_user, conversation_id, message_id)
        return success_message("已删除")

    # ---------- name (/conversations/<id>/name) ----------

    @RequireLogin
    def get_name(self, conversation_id: int):
        return success({"name": self.conversation_service.get_name(current_user, conversation_id)})

    @RequireLogin
    def update_name(self, conversation_id: int):
        try:
            req = ConversationRenameReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        conv = self.conversation_service.rename(current_user, conversation_id, req.name)
        return success(ConversationItem.model_validate(conv).model_dump(mode="json"))

    # ---------- pinned ----------

    @RequireLogin
    def update_is_pinned(self, conversation_id: int):
        try:
            req = ConversationIsPinnedReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        conv = self.conversation_service.update_is_pinned(current_user, conversation_id, req.is_pinned)
        return success(ConversationItem.model_validate(conv).model_dump(mode="json"))
