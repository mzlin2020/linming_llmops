"""带历史的 chat 流程。

两条对话链路共用同一套流式/同步内核（_stream / _complete），仅「配置来源」「会话 silo」不同：
- debug（编排预览）：读 **草稿配置** app.draft_app_config，会话走 get_or_create_for_app（invoke_from=web_app）
- published（与已发布应用对话）：读 **已发布配置** app.app_config，会话走 get_or_create_published_for_app（invoke_from=published）

落库时机：append_round（开一轮）→ SSE → finally finalize_round（回写 answer/latency/status）。
SSE 协议：每帧 `event: <name>\\ndata: <JSON>\\n\\n`，不再有裸 data 或 [DONE]。

注：工作流-as-工具（config.workflows）经 WorkflowService.get_langchain_tools_by_ids 实时解析
（按 已发布 + 归属本人 过滤）后追加到 Agent 工具列表，与 config.tools / config.datasets 并列。
"""
import uuid
from dataclasses import dataclass
from typing import Generator, Optional

from injector import inject

from internal.core.agent import ToolResolver
from internal.core.language_model.language_model_manager import LanguageModelManager
from internal.entity import InvokeFrom, RetrievalSource
from internal.exception import ForbiddenException, ValidateErrorException
from internal.model import Account, App, Conversation
from internal.schema.chat_schema import DebugChatReq
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
    compose_system_prompt,
    ltm_enabled,
    resolve_provider_model,
)
from internal.service.app_service import AppService
from internal.service.conversation_service import HISTORY_TURNS_CAP, ConversationService
from internal.service.quota_service import QuotaService
from internal.service.retrieval_service import RetrievalService
from internal.service.workflow_service import WorkflowService


@inject
@dataclass
class ChatService:
    app_service: AppService
    conversation_service: ConversationService
    llm_manager: LanguageModelManager
    tool_resolver: ToolResolver
    retrieval_service: RetrievalService
    quota_service: QuotaService
    workflow_service: WorkflowService

    # ---------- debug（编排预览，读草稿配置）----------

    def debug_chat(self, user: Account, app_id: int, req: DebugChatReq) -> Generator[str, None, None]:
        app, conv = self._prepare(user, app_id, req.conversation_id)
        config = app.draft_app_config
        return self._stream(user, app, conv, config, req, InvokeFrom.WEB_APP.value,
                            history_cap=self._history_cap_from(config))

    def complete_chat(self, user: Account, app_id: int, req: DebugChatReq) -> dict:
        app, conv = self._prepare(user, app_id, req.conversation_id)
        config = app.draft_app_config
        return self._complete(user, app, conv, config, req, InvokeFrom.WEB_APP.value,
                              history_cap=self._history_cap_from(config))

    # ---------- published（与已发布应用对话，读已发布配置）----------

    def published_chat(self, user: Account, app_id: int, req: DebugChatReq) -> Generator[str, None, None]:
        app, config, conv = self._prepare_published(user, app_id, req.conversation_id)
        return self._stream(user, app, conv, config, req, InvokeFrom.PUBLISHED.value,
                            history_cap=self._history_cap_from(config))

    def published_complete(self, user: Account, app_id: int, req: DebugChatReq) -> dict:
        app, config, conv = self._prepare_published(user, app_id, req.conversation_id)
        return self._complete(user, app, conv, config, req, InvokeFrom.PUBLISHED.value,
                              history_cap=self._history_cap_from(config))

    def stop_debug_chat(self, user: Account, app_id: int, task_id: str) -> None:
        """真·停止：先校验 user 对 app 的归属，再按 task_id 归属置 redis 停止 flag。
        Agent 流式 generator 每帧查该 flag，可秒级中断；非 Agent（裸 LLM 流）无 task 登记，自然 no-op。"""
        self.app_service.get(user, app_id)
        request_stop(task_id, user.id)
        return

    # ---------- 共享内核 ----------

    def _stream(
        self, user: Account, app: App, conv: Conversation, config, req: DebugChatReq, invoke_from: str,
        *, end_user_id: Optional[int] = None, history_cap: int = HISTORY_TURNS_CAP,
    ) -> Generator[str, None, None]:
        """SSE generator。前置工作（鉴权 / 准备会话 / 建消息行）在 view 上下文同步完成，
        generator 内只跑 LLM stream + finalize。config 为草稿/已发布配置行（带 preset_prompt/model_config）。
        end_user_id / history_cap 仅开放 API（service_api）传入：站内入口不传 → 行为与改造前完全一致
        （end_user_id 为 None、历史走默认 HISTORY_TURNS_CAP）。"""
        conv_id = conv.id
        system_prompt = compose_system_prompt(config, conv)
        ltm_on = ltm_enabled(config)
        history = self.conversation_service.history_for_llm(conv, cap_turns=history_cap)
        provider, model_name = resolve_provider_model(config)
        image_urls, file_infos, vision_ok = prepare_attachments(
            self.llm_manager, self.quota_service, user, req, provider, model_name,
        )
        msg = self.conversation_service.append_round(
            conv_id, app_id=app.id, user_id=user.id,
            query=req.query, image_urls=image_urls, file_infos=file_infos,
            invoke_from=invoke_from, end_user_id=end_user_id,
        )
        msg_id = msg.id

        lc_messages = build_lc_messages(
            system_prompt, history, req.query,
            image_urls=image_urls, file_infos=file_infos, supports_vision=vision_ok,
        )
        llm = self.llm_manager.instantiate(provider, model_name)
        task_id = str(uuid.uuid4())

        tools = self._build_tools(config, user, app, provider, model_name)
        if tools:
            return run_agent_stream(
                conversation_service=self.conversation_service,
                llm=llm, tools=tools, tool_call_supported=True,
                lc_messages=lc_messages, conv_id=conv_id, msg_id=msg_id,
                app_id=app.id, user_id=user.id, invoke_from=invoke_from,
                provider=provider, model_name=model_name, task_id=task_id,
                long_term_memory_enabled=ltm_on,
            )

        return run_llm_stream(
            conversation_service=self.conversation_service,
            llm=llm, lc_messages=lc_messages, conv_id=conv_id, msg_id=msg_id,
            provider=provider, model_name=model_name, task_id=task_id,
            long_term_memory_enabled=ltm_on,
        )

    def _complete(
        self, user: Account, app: App, conv: Conversation, config, req: DebugChatReq, invoke_from: str,
        *, end_user_id: Optional[int] = None, history_cap: int = HISTORY_TURNS_CAP,
    ) -> dict:
        """同步版：一次性调 llm.invoke，写一条 ai_message。
        end_user_id / history_cap 仅开放 API 传入；站内入口不传 → 行为与改造前一致。"""
        conv_id = conv.id
        system_prompt = compose_system_prompt(config, conv)
        ltm_on = ltm_enabled(config)
        history = self.conversation_service.history_for_llm(conv, cap_turns=history_cap)
        provider, model_name = resolve_provider_model(config)
        image_urls, file_infos, vision_ok = prepare_attachments(
            self.llm_manager, self.quota_service, user, req, provider, model_name,
        )
        msg = self.conversation_service.append_round(
            conv_id, app_id=app.id, user_id=user.id,
            query=req.query, image_urls=image_urls, file_infos=file_infos,
            invoke_from=invoke_from, end_user_id=end_user_id,
        )

        lc_messages = build_lc_messages(
            system_prompt, history, req.query,
            image_urls=image_urls, file_infos=file_infos, supports_vision=vision_ok,
        )
        llm = self.llm_manager.instantiate(provider, model_name)

        tools = self._build_tools(config, user, app, provider, model_name)
        if tools:
            return run_agent_complete(
                conversation_service=self.conversation_service,
                llm=llm, tools=tools, tool_call_supported=True,
                lc_messages=lc_messages, conv_id=conv_id, msg_id=msg.id,
                app_id=app.id, user_id=user.id, invoke_from=invoke_from,
                provider=provider, model_name=model_name, query=req.query,
                long_term_memory_enabled=ltm_on,
            )

        return run_llm_complete(
            conversation_service=self.conversation_service,
            llm=llm, lc_messages=lc_messages, conv_id=conv_id, msg_id=msg.id,
            provider=provider, model_name=model_name, query=req.query,
            long_term_memory_enabled=ltm_on,
        )

    # ---------- internal ----------

    @staticmethod
    def _history_cap_from(config) -> int:
        """站内链路的历史轮数：配置了 dialog_round 用它（0 = 不带历史），缺省回默认 cap。
        openapi 不走这里（用服务端变量 OPENAPI_HISTORY_MAX_TURNS）。"""
        dr = getattr(config, "dialog_round", None)
        if dr is None:
            return HISTORY_TURNS_CAP
        try:
            return max(0, min(int(dr), 100))
        except (TypeError, ValueError):
            return HISTORY_TURNS_CAP

    def _build_tools(self, config, user: Account, app: App, provider: str, model_name: str) -> list:
        """解析 config.tools，并按 config.datasets 追加一个 dataset_retrieval 知识库检索工具；
        返回可直接交给 Agent 的工具列表——模型不支持 tool_call 时返回 []，调用方据此降级为裸 LLM。
        只有按-app chat 走这里，assistant-agent 是另一份装配逻辑，不受影响。

        检索不计命中配额（与灌库/重索引不同，检索查询几乎不增内存）。归属由 retrieval_service 二次过滤兜底。
        config.datasets 落库时已由 AppConfigService._validate_datasets 规整为去重的自有库 int id 列表，此处直接信任。
        config.workflows（工作流-as-工具）经 WorkflowService 实时解析（已发布 + 归属本人）后追加；
        config.workflows 落库时已由 AppConfigService._validate_workflows 规整为去重的自有已发布 int id 列表。"""
        if not self.llm_manager.supports_tool_call(provider, model_name):
            return []
        tools = self.tool_resolver.resolve(
            getattr(config, "tools", None), is_admin=bool(getattr(user, "is_admin", False)),
        )
        dataset_ids = [d for d in (getattr(config, "datasets", None) or []) if isinstance(d, int)]
        if dataset_ids:
            tools.append(self.retrieval_service.create_langchain_tool_from_search(
                dataset_ids=dataset_ids, user_id=user.id,
                source=RetrievalSource.APP.value, source_app_id=app.id,
            ))
        workflow_ids = [w for w in (getattr(config, "workflows", None) or []) if isinstance(w, int)]
        if workflow_ids:
            tools.extend(self.workflow_service.get_langchain_tools_by_ids(workflow_ids, user))
        return tools

    def _prepare(
        self, user: Account, app_id: int, conversation_id: Optional[int],
    ) -> tuple[App, Conversation]:
        app = self.app_service.get(user, app_id)
        if conversation_id is None:
            conv = self.conversation_service.get_or_create_for_app(user, app)
        else:
            conv = self.conversation_service.get(user, conversation_id)
            if conv.app_id != app.id:
                raise ForbiddenException("会话与 app 不匹配")
        return app, conv

    def _prepare_published(
        self, user: Account, app_id: int, conversation_id: Optional[int],
    ) -> tuple[App, object, Conversation]:
        app = self.app_service.get(user, app_id)
        config = app.app_config
        if config is None:
            raise ValidateErrorException(message="该应用尚未发布，无法对话")
        if conversation_id is None:
            conv = self.conversation_service.get_or_create_published_for_app(user, app)
        else:
            conv = self.conversation_service.get(user, conversation_id)
            if conv.app_id != app.id:
                raise ForbiddenException("会话与 app 不匹配")
        return app, config, conv
