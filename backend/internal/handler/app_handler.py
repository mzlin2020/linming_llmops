"""AppHandler：应用 CRUD + 草稿/发布配置 + 公共应用商店 + 调试/已发布对话(SSE) + 长期记忆。

全部要求登录。请求体/查询参数用 pydantic v2 解析；SSE 流式经 pkg.response.compact_generate_response 包裹。
"""
from dataclasses import dataclass

from flask import request
from flask_login import current_user
from injector import inject
from pydantic import ValidationError

from internal.exception import ValidateErrorException
from internal.lib.helper import first_validation_error as _first_error
from internal.middleware import RequireLogin
from internal.schema.app_schema import (
    AppConfigItem,
    AppCreateReq,
    AppItem,
    AppUpdateReq,
    DebugConversationSummaryReq,
    FallbackHistoryReq,
    GetAppStoreWithPageReq,
    PublishAppReq,
)
from internal.schema.chat_schema import DebugChatReq
from internal.schema.conversation_schema import GetMessagesWithPageReq, PaginatorReq
from internal.service import AppService, ChatService, ConversationService
from pkg.response import compact_generate_response, success, success_message


@inject
@dataclass
class AppHandler:
    app_service: AppService
    chat_service: ChatService
    conversation_service: ConversationService

    # ---------- 出参拼装 ----------

    def _app_item(self, app) -> dict:
        """应用基础信息 + 从草稿行合并 preset/model/dialog。"""
        body = AppItem.model_validate(app).model_dump(mode="json", by_alias=True)
        draft = app.draft_app_config
        body["preset_prompt"] = draft.preset_prompt
        body["model_config"] = draft.model_config
        body["dialog_round"] = draft.dialog_round
        return body

    # ---------- App CRUD ----------

    @RequireLogin
    def list_apps(self):
        # 仅返回用户自己的应用（含其自动创建的「默认助手」）；全局内置辅助 Agent 不混入此列表
        items = self.app_service.list_by_user(current_user)
        return success([self._app_item(a) for a in items])

    @RequireLogin
    def create_app(self):
        try:
            req = AppCreateReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        app = self.app_service.create(current_user, req)
        return success(self._app_item(app))

    @RequireLogin
    def default(self):
        """GET /apps/default —— 取当前用户的默认 app；不存在则创建。"""
        app = self.app_service.get_or_create_default(current_user)
        return success(self._app_item(app))

    @RequireLogin
    def get_app(self, app_id: int):
        app = self.app_service.get(current_user, app_id)
        body = self._app_item(app)
        # 详情附带配置全集（取自草稿行）
        body["app_config"] = AppConfigItem.model_validate(
            app.draft_app_config
        ).model_dump(mode="json", by_alias=True)
        # 是否已上架公共应用商店（编排页开关回显；仅详情查，列表不查避免 N+1）
        body["is_public"] = self.app_service.is_app_public(app.id)
        return success(body)

    @RequireLogin
    def update_app(self, app_id: int):
        try:
            req = AppUpdateReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        app = self.app_service.update(current_user, app_id, req)
        return success(self._app_item(app))

    @RequireLogin
    def delete_app(self, app_id: int):
        self.app_service.delete(current_user, app_id)
        return success_message("已删除")

    @RequireLogin
    def copy_app(self, app_id: int):
        """POST /apps/<id>/copy —— 复制一个应用（草稿配置一并拷贝，新应用未发布）。"""
        app = self.app_service.copy(current_user, app_id)
        return success(self._app_item(app))

    # ---------- 草稿配置 ----------

    @RequireLogin
    def get_draft_app_config(self, app_id: int):
        """GET /apps/<id>/draft-app-config —— 取草稿配置（编排页加载）。"""
        return success(self.app_service.get_draft_app_config(current_user, app_id))

    @RequireLogin
    def update_draft_app_config(self, app_id: int):
        """POST /apps/<id>/draft-app-config —— 原地更新草稿配置。"""
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            raise ValidateErrorException(message="参数错误")
        return success(self.app_service.update_draft_app_config(current_user, app_id, payload))

    # ---------- 发布 / 取消发布 ----------

    @RequireLogin
    def publish(self, app_id: int):
        """POST /apps/<id>/publish —— 发布草稿配置为运行配置，追加一条发布历史。"""
        app = self.app_service.publish_draft_app_config(current_user, app_id)
        return success(self._app_item(app))

    @RequireLogin
    def cancel_publish(self, app_id: int):
        """POST /apps/<id>/cancel-publish —— 取消发布。"""
        app = self.app_service.cancel_publish_app_config(current_user, app_id)
        return success(self._app_item(app))

    # ---------- 公共应用商店 ----------

    @RequireLogin
    def get_app_store(self):
        """GET /api/app-store —— 公共应用商店分页列表（含「是否已添加」标记）。"""
        try:
            req = GetAppStoreWithPageReq.model_validate(request.args.to_dict(flat=True))
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        return success(self.app_service.get_app_store_with_page(req, current_user))

    @RequireLogin
    def publish_app_to_store(self, app_id: int):
        """POST /api/apps/<app_id>/store-publish —— 上架 / 下架公共应用商店
        （任意登录用户对自己已发布的应用）。"""
        try:
            req = PublishAppReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        self.app_service.set_app_public(app_id, req.is_public, current_user)
        return success_message("已上架到应用商店" if req.is_public else "已从应用商店下架")

    @RequireLogin
    def add_store_app_to_me(self, public_id: int):
        """POST /api/app-store/<public_id>/add —— 复制一份公共应用到我的应用列表。"""
        app = self.app_service.add_app_to_me(public_id, current_user)
        return success(self._app_item(app))

    # ---------- 版本历史 / 回退 ----------

    @RequireLogin
    def get_publish_histories(self, app_id: int):
        """GET /apps/<id>/publish-histories —— 发布历史（分页，version 降序）。"""
        try:
            req = PaginatorReq.model_validate(request.args.to_dict(flat=True))
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        page = self.app_service.get_publish_histories_with_page(
            current_user, app_id, req.current_page, req.page_size,
        )
        return success(page.model_dump(mode="json"))

    @RequireLogin
    def fallback_history(self, app_id: int):
        """POST /apps/<id>/fallback-history —— 回退某历史版本到草稿。"""
        try:
            req = FallbackHistoryReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        config = self.app_service.fallback_history_to_draft(
            current_user, app_id, req.app_config_version_id,
        )
        return success(config)

    @RequireLogin
    def get_published_config(self, app_id: int):
        """GET /apps/<id>/published-config —— 取已发布配置；未发布返回 null。"""
        return success(self.app_service.get_published_config(current_user, app_id))

    # ---------- Chat（调试，读草稿）----------

    def _parse_chat_req(self) -> DebugChatReq:
        try:
            return DebugChatReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))

    @RequireLogin
    def debug_chat(self, app_id: int):
        """POST /apps/<app_id>/conversations —— SSE 流式聊天（读草稿配置）。"""
        req = self._parse_chat_req()
        gen = self.chat_service.debug_chat(current_user, app_id, req)
        return compact_generate_response(gen)

    @RequireLogin
    def complete_chat(self, app_id: int):
        """POST /apps/<app_id>/conversations/complete —— 同步版（读草稿配置）。"""
        req = self._parse_chat_req()
        return success(self.chat_service.complete_chat(current_user, app_id, req))

    @RequireLogin
    def stop_debug_chat(self, app_id: int, task_id: str):
        """POST /apps/<app_id>/conversations/tasks/<task_id>/stop —— 中断该 task 的 Agent 流式生成。"""
        self.chat_service.stop_debug_chat(current_user, app_id, task_id)
        return success_message("ok")

    @RequireLogin
    def debug_messages(self, app_id: int):
        """GET /apps/<app_id>/conversations/messages —— 分页拉该 app 调试会话的消息。"""
        try:
            req = GetMessagesWithPageReq.model_validate(request.args.to_dict(flat=True))
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        app = self.app_service.get(current_user, app_id)
        conv = self.conversation_service.get_or_create_for_app(current_user, app)
        page = self.conversation_service.list_messages_with_page(current_user, conv.id, req)
        return success(page.model_dump(mode="json"))

    @RequireLogin
    def delete_debug_conversation(self, app_id: int):
        """POST /apps/<app_id>/conversations/delete-debug-conversation —— 软删该 user × app 全部会话。"""
        self.app_service.delete_debug_conversation(current_user, app_id)
        return success_message("ok")

    # ---------- 与已发布应用对话（读已发布配置）----------

    @RequireLogin
    def published_chat(self, app_id: int):
        """POST /apps/<app_id>/published-conversations —— SSE 流式（读已发布配置）。"""
        req = self._parse_chat_req()
        gen = self.chat_service.published_chat(current_user, app_id, req)
        return compact_generate_response(gen)

    @RequireLogin
    def published_complete(self, app_id: int):
        """POST /apps/<app_id>/published-conversations/complete —— 同步版（读已发布配置）。"""
        req = self._parse_chat_req()
        return success(self.chat_service.published_complete(current_user, app_id, req))

    @RequireLogin
    def published_messages(self, app_id: int):
        """GET /apps/<app_id>/published-conversations/messages —— 分页拉已发布对话消息。"""
        try:
            req = GetMessagesWithPageReq.model_validate(request.args.to_dict(flat=True))
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        app = self.app_service.get(current_user, app_id)
        conv = self.conversation_service.get_or_create_published_for_app(current_user, app)
        page = self.conversation_service.list_messages_with_page(current_user, conv.id, req)
        return success(page.model_dump(mode="json"))

    @RequireLogin
    def clear_published_conversation(self, app_id: int):
        """POST /apps/<app_id>/published-conversations/clear —— 清空已发布对话历史（仅抹消息，保留长期记忆）。"""
        app = self.app_service.get(current_user, app_id)
        self.conversation_service.clear_published_messages(current_user, app)
        return success_message("ok")

    # ---------- 长期记忆 ----------

    @RequireLogin
    def get_summary(self, app_id: int):
        return success({"summary": self.app_service.get_summary(current_user, app_id)})

    @RequireLogin
    def update_summary(self, app_id: int):
        try:
            req = DebugConversationSummaryReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        self.app_service.update_summary(current_user, app_id, req.summary)
        return success_message("ok")
