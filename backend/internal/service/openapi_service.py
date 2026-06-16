"""开放 API（service_api）聊天服务——薄封装。

只做开放 API 特有的「鉴权后定位 published app + 校验/建终端用户 + 校验/建会话」，
对话本身直接委托现成内核 ChatService._stream / _complete（不重抄一遍）。

与站内聊天的差异：
- 配置来源：已发布运行配置 app.app_config（必须 PUBLISHED）。
- 会话 silo：invoke_from=service_api，按 end_user 隔离（end_user_id 校验归属）。
- 历史轮数：由服务端变量 OPENAPI_HISTORY_MAX_TURNS 决定，调用方请求体不含轮数字段、无法覆盖
  （防外部塞大轮数把 token 成本打爆）。
"""
from dataclasses import dataclass
from typing import Generator, Union

from flask import current_app
from injector import inject

from internal.entity import InvokeFrom, QueueEvent
from internal.entity.app_entity import AppStatus
from internal.exception import ForbiddenException, NotFoundException
from internal.extension.database_extension import db
from internal.model import Account, App, AppConfig, Conversation, EndUser
from internal.schema.openapi_schema import OpenAPIChatReq
from internal.service._chat_common import sse as _sse
from internal.service.app_service import AppService
from internal.service.chat_service import ChatService
from internal.service.conversation_service import ConversationService
from internal.service.quota_service import QuotaService
from pkg.response import Response


@inject
@dataclass
class OpenAPIService:
    app_service: AppService
    conversation_service: ConversationService
    chat_service: ChatService
    quota_service: QuotaService

    def _get_published(self, account: Account, app_id: int) -> tuple[App, AppConfig]:
        """开放 API 的统一闸门：定位应用（归属校验在 app_service.get）+「必须已发布」，
        返回 (app, 已发布运行配置)。所有开放 API 端点都从这里进，发布语义只此一处。"""
        app = self.app_service.get(account, app_id)
        if app.status != AppStatus.PUBLISHED.value:
            raise NotFoundException("该应用不存在或未发布，请核实后重试")
        config = app.app_config
        if config is None:
            raise NotFoundException("该应用尚未发布，无法对话")
        return app, config

    def app_info(self, account: Account, app_id: int) -> dict:
        """返回已发布应用的对外展示元信息：开场白 / 开场建议问题。

        供开放 API 调用方渲染空状态用，不触发任何 LLM 调用、不计配额。
        opening_questions 在发布路径已清洗（str + 截断 + 上限 5 条），这里原样透出。
        """
        app, config = self._get_published(account, app_id)
        return {
            "name": app.name,
            "opening_statement": config.opening_statement or "",
            "opening_questions": config.opening_questions or [],
        }

    def chat(self, req: OpenAPIChatReq, account: Account) -> Union[Response, Generator[str, None, None]]:
        """account = 钥匙归属人（由 openapi 蓝图的 API key 鉴权填充的 current_user）。"""
        # 0.限速（按账号）。早于一切业务：失败请求也计数、被限时不碰 DB，
        #   且在构建 SSE 生成器之前抛 429，stream 请求也能拿到干净的 429 JSON。
        self.quota_service.check_openapi_chat(account)

        # 1-2.定位 app + 必须已发布（归属校验在 app_service.get：非 owner 抛 404）
        app, config = self._get_published(account, req.app_id)

        # 3.终端用户：传了则校验归属，没传则建一个匿名终端用户
        if req.end_user_id is not None:
            end_user = db.session.get(EndUser, req.end_user_id)
            if not end_user or end_user.app_id != app.id or end_user.user_id != account.id:
                raise ForbiddenException("终端用户不存在或不属于该应用，请核实后重试")
        else:
            end_user = self._create_end_user(account, app)

        # 4.会话：传了则校验归属（app/调用方式/终端用户三者匹配），没传则建 service_api 会话
        if req.conversation_id is not None:
            conv = db.session.get(Conversation, req.conversation_id)
            if (
                not conv
                or conv.is_deleted
                or conv.app_id != app.id
                or conv.invoke_from != InvokeFrom.SERVICE_API.value
                or conv.end_user_id != end_user.id
            ):
                raise ForbiddenException("该会话不存在，或者不属于该应用/终端用户/调用方式")
        else:
            conv = self.conversation_service.create(
                account, app, title="New Conversation",
                invoke_from=InvokeFrom.SERVICE_API.value, end_user_id=end_user.id,
            )

        # 5.历史轮数上限——服务端口径，调用方不可覆盖
        history_cap = int(current_app.config["OPENAPI_HISTORY_MAX_TURNS"])

        # 快照成纯 int，供生成器在请求上下文结束后安全引用
        conv_id, end_user_id = conv.id, end_user.id

        # 6.委托现成内核；stream 决定 SSE 生成器 / 一次性 Response。
        # 两种模式都把 end_user_id 回给调用方——复用会话时必须带它（见 schema 校验）。
        if req.stream:
            inner = self.chat_service._stream(
                account, app, conv, config, req, InvokeFrom.SERVICE_API.value,
                end_user_id=end_user_id, history_cap=history_cap,
            )

            def _with_meta():
                # 先发一帧 ping 携带 conversation_id / end_user_id，便于调用方记录用于后续复用
                yield _sse(QueueEvent.PING, {"conversation_id": conv_id, "end_user_id": end_user_id})
                yield from inner

            return _with_meta()

        result = self.chat_service._complete(
            account, app, conv, config, req, InvokeFrom.SERVICE_API.value,
            end_user_id=end_user_id, history_cap=history_cap,
        )
        return Response(data={**result, "end_user_id": end_user_id})

    def _create_end_user(self, account: Account, app: App) -> EndUser:
        with db.auto_commit():
            end_user = EndUser(user_id=account.id, app_id=app.id)
            db.session.add(end_user)
        db.session.refresh(end_user)
        return end_user
