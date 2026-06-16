"""辅助 Agent：单会话聊天。

与 ChatService（多会话）的区别：
- app 是全局共享的内置 app（user_id 为 NULL），由 AppService.get_or_create_assistant_agent_app 兜底。
- 每个用户在该 app 下永远只有「一条」当前会话：按 created_by + invoke_from='assistant_agent'
  + is_deleted=False 取最新一条；无则建（隔离靠 created_by，绝不跨用户串话）。
- 清空 = 软删当前用户的全部辅助 Agent 会话；下次 chat 时自然新建一条。

复用 ConversationService 的 history_for_llm / append_round / finalize_round /
list_messages_with_page，以及 _chat_common 的 sse / build_lc_messages / resolve_provider_model。
"""
import uuid
from dataclasses import dataclass
from typing import Generator, Optional

from injector import inject
from sqlalchemy import desc, select

from internal.core.agent import ToolResolver
from internal.core.language_model.language_model_manager import LanguageModelManager
from internal.entity import InvokeFrom
from internal.exception import ValidateErrorException
from internal.extension.database_extension import db
from internal.model import Account, App, Conversation
from internal.schema.assistant_agent_schema import AssistantAgentChatReq
from internal.schema.conversation_schema import GetMessagesWithPageReq, PageModel
from internal.service._agent_runtime import (
    request_stop,
    run_agent_complete,
    run_agent_stream,
    run_llm_complete,
    run_llm_stream,
)
from internal.service._chat_attachments import prepare_attachments
from internal.service._chat_common import (
    build_lc_messages,
    resolve_provider_model,
)
from internal.service.app_service import AppService
from internal.service.conversation_service import ConversationService
from internal.service.quota_service import QuotaService

_INVOKE = InvokeFrom.ASSISTANT_AGENT.value


@inject
@dataclass
class AssistantAgentService:
    app_service: AppService
    conversation_service: ConversationService
    llm_manager: LanguageModelManager
    tool_resolver: ToolResolver
    quota_service: QuotaService

    # ---------- public ----------

    def chat(self, user: Account, req: AssistantAgentChatReq) -> Generator[str, None, None]:
        """SSE 流式。前置（取 app / 取或建会话 / 建消息行）在 view 上下文同步完成，
        generator 内只跑 LLM stream + finalize。"""
        app, conv = self._get_or_create_conversation(user)
        config = app.draft_app_config  # 取一次：人设 / 工具 / 默认模型都读它
        conv_id = conv.id
        system_prompt = config.preset_prompt or ""
        history = self.conversation_service.history_for_llm(conv)
        provider, model_name = self._pick_model(config, req)
        image_urls, file_infos, vision_ok = prepare_attachments(
            self.llm_manager, self.quota_service, user, req, provider, model_name,
        )
        msg = self.conversation_service.append_round(
            conv_id, app_id=app.id, user_id=user.id,
            query=req.query, image_urls=image_urls, file_infos=file_infos, invoke_from=_INVOKE,
        )
        msg_id = msg.id

        lc_messages = build_lc_messages(
            system_prompt, history, req.query,
            image_urls=image_urls, file_infos=file_infos, supports_vision=vision_ok,
        )
        llm = self.llm_manager.instantiate(provider, model_name)
        task_id = str(uuid.uuid4())

        tools = self.tool_resolver.resolve(
            getattr(config, "tools", None), is_admin=bool(getattr(user, "is_admin", False)),
        )
        if tools and self.llm_manager.supports_tool_call(provider, model_name):
            return run_agent_stream(
                conversation_service=self.conversation_service,
                llm=llm, tools=tools, tool_call_supported=True,
                lc_messages=lc_messages, conv_id=conv_id, msg_id=msg_id,
                app_id=app.id, user_id=user.id, invoke_from=_INVOKE,
                provider=provider, model_name=model_name, task_id=task_id,
            )

        # 辅助 Agent 标题固定（不在 AUTO_NAME_TITLES）、无长期记忆，故收尾恒为 no-op，仍走统一 enqueue 收口
        return run_llm_stream(
            conversation_service=self.conversation_service,
            llm=llm, lc_messages=lc_messages, conv_id=conv_id, msg_id=msg_id,
            provider=provider, model_name=model_name, task_id=task_id,
        )

    def complete(self, user: Account, req: AssistantAgentChatReq) -> dict:
        """同步版：一次性调 llm.invoke，写一条 ai_message。"""
        app, conv = self._get_or_create_conversation(user)
        config = app.draft_app_config  # 取一次：人设 / 工具 / 默认模型都读它
        conv_id = conv.id
        system_prompt = config.preset_prompt or ""
        history = self.conversation_service.history_for_llm(conv)
        provider, model_name = self._pick_model(config, req)
        image_urls, file_infos, vision_ok = prepare_attachments(
            self.llm_manager, self.quota_service, user, req, provider, model_name,
        )
        msg = self.conversation_service.append_round(
            conv_id, app_id=app.id, user_id=user.id,
            query=req.query, image_urls=image_urls, file_infos=file_infos, invoke_from=_INVOKE,
        )

        lc_messages = build_lc_messages(
            system_prompt, history, req.query,
            image_urls=image_urls, file_infos=file_infos, supports_vision=vision_ok,
        )
        llm = self.llm_manager.instantiate(provider, model_name)

        tools = self.tool_resolver.resolve(
            getattr(config, "tools", None), is_admin=bool(getattr(user, "is_admin", False)),
        )
        if tools and self.llm_manager.supports_tool_call(provider, model_name):
            return run_agent_complete(
                conversation_service=self.conversation_service,
                llm=llm, tools=tools, tool_call_supported=True,
                lc_messages=lc_messages, conv_id=conv_id, msg_id=msg.id,
                app_id=app.id, user_id=user.id, invoke_from=_INVOKE,
                provider=provider, model_name=model_name, query=req.query,
            )

        return run_llm_complete(
            conversation_service=self.conversation_service,
            llm=llm, lc_messages=lc_messages, conv_id=conv_id, msg_id=msg.id,
            provider=provider, model_name=model_name, query=req.query,
        )

    def list_messages(self, user: Account, req: GetMessagesWithPageReq) -> PageModel:
        """分页拉当前会话历史；无会话时返回空页。"""
        conv = self._current_conversation(user)
        if conv is None:
            return PageModel(
                list=[],
                paginator={
                    "current_page": req.current_page,
                    "page_size": req.page_size,
                    "total_page": 0,
                    "total_record": 0,
                },
            )
        return self.conversation_service.list_messages_with_page(user, conv.id, req)

    def clear_conversation(self, user: Account) -> None:
        """软删该用户全部辅助 Agent 会话；下次 chat 时 _get_or_create_conversation 自然新建。
        只删 invoke_from='assistant_agent' 的会话，绝不波及用户的多会话(web_app)数据。"""
        app = self.app_service.get_or_create_assistant_agent_app()
        with db.auto_commit():
            db.session.query(Conversation).filter(
                Conversation.app_id == app.id,
                Conversation.created_by == user.id,
                Conversation.invoke_from == _INVOKE,
                Conversation.is_deleted.is_(False),
            ).update({Conversation.is_deleted: True}, synchronize_session=False)

    def stop(self, user: Account, task_id: str) -> None:
        """真·停止：按 task_id 归属置 redis 停止 flag（防跨用户）。
        Agent 流式 generator 每帧查该 flag 中断；非 Agent 裸流无 task 登记，自然 no-op。"""
        request_stop(task_id, user.id)
        return

    # ---------- internal ----------

    def _pick_model(self, config, req: AssistantAgentChatReq) -> tuple[str, str]:
        """本轮模型：请求显式指定(且经注册表校验合法)则用之，否则回退配置/env 默认。
        在 view 上下文内调用，非法模型直接抛异常 → 干净的错误响应，不会进入 SSE 流。"""
        if req.provider and req.model:
            self.llm_manager.get_model_entity(req.provider, req.model)  # 非法→NotFoundException
            return req.provider, req.model
        if req.provider or req.model:
            raise ValidateErrorException(message="provider 与 model 须成对传递")
        return resolve_provider_model(config)

    def _current_conversation(self, user: Account) -> Optional[Conversation]:
        """该用户当前（最新未删）的辅助 Agent 会话；无则 None。"""
        app = self.app_service.get_or_create_assistant_agent_app()
        return self._latest_conv(app, user)

    def _get_or_create_conversation(self, user: Account) -> tuple[App, Conversation]:
        app = self.app_service.get_or_create_assistant_agent_app()
        conv = self._latest_conv(app, user)
        if conv is None:
            conv = self.conversation_service.create(
                user, app, title="AI 助手", invoke_from=_INVOKE,
            )
        return app, conv

    @staticmethod
    def _latest_conv(app: App, user: Account) -> Optional[Conversation]:
        """该 app × user 下最新一条未删的辅助 Agent 会话（invoke_from='assistant_agent'）；无则 None。"""
        stmt = (
            select(Conversation)
            .where(
                Conversation.app_id == app.id,
                Conversation.created_by == user.id,
                Conversation.invoke_from == _INVOKE,
                Conversation.is_deleted.is_(False),
            )
            .order_by(desc(Conversation.updated_at))
            .limit(1)
        )
        return db.session.scalars(stmt).first()
