"""会话与消息持久化。

权限边界：conversation 的所有访问都要校验 user 是 owner（与 AppService 同款规则）。
一行 ai_message = 一轮 (query + answer)。delete 走软删，list 时过滤 is_deleted。
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from injector import inject
from sqlalchemy import desc, func, select

from internal.core.language_model.language_model_manager import LanguageModelManager
from internal.entity import (
    CONVERSATION_NAME_TEMPLATE,
    SUMMARIZER_TEMPLATE,
    InvokeFrom,
    MessageStatus,
)
from internal.exception import ForbiddenException, NotFoundException
from internal.extension.database_extension import db
from internal.model import Account, App, Conversation, Message
from internal.schema.conversation_schema import GetMessagesWithPageReq, MessageItem, PageModel
from internal.service._chat_common import HistoryTurn, build_lc_messages, extract_text
from pkg.paginator import Paginator

# 拼进 LLM 输入的最大历史回合数（一行 = 一轮，故 = 历史消息数）。
HISTORY_TURNS_CAP = 20
# 长期记忆摘要的硬上限（与 prompt 里 2000 字符约束留点余量）。
_SUMMARY_MAX_CHARS = 4000
# 仅对仍是默认标题的会话自动命名；"已发布应用对话"/"AI 助手" 等固定标题天然排除。
AUTO_NAME_TITLES = {"新会话"}
# 自动生成标题的长度上限（与 ai_conversation.title 列 VARCHAR(128) 对齐）。
_TITLE_MAX_CHARS = 128


@inject
@dataclass
class ConversationService:
    llm_manager: LanguageModelManager

    # ---------- conversation ----------

    def create(
        self, user: Account, app: App, title: str = "新会话", invoke_from: str = "web_app",
        end_user_id: Optional[int] = None,
    ) -> Conversation:
        with db.auto_commit():
            conv = Conversation(
                app_id=app.id,
                user_id=user.id,
                title=title,
                invoke_from=invoke_from,
                created_by=user.id,
                end_user_id=end_user_id,
            )
            db.session.add(conv)
        db.session.refresh(conv)
        return conv

    def get(self, user: Account, conversation_id: int) -> Conversation:
        conv = db.session.get(Conversation, conversation_id)
        if not conv or conv.is_deleted:
            raise NotFoundException("会话不存在")
        if conv.user_id != user.id and not user.is_admin:
            raise ForbiddenException("无权访问该会话")
        return conv

    def list_by_user(self, user: Account, app_id: Optional[int] = None, limit: int = 50) -> list[Conversation]:
        stmt = select(Conversation).where(
            Conversation.user_id == user.id,
            Conversation.is_deleted.is_(False),
        )
        if app_id is not None:
            stmt = stmt.where(Conversation.app_id == app_id)
        stmt = stmt.order_by(desc(Conversation.is_pinned), desc(Conversation.updated_at)).limit(limit)
        return list(db.session.scalars(stmt))

    def delete(self, user: Account, conversation_id: int) -> None:
        conv = self.get(user, conversation_id)
        with db.auto_commit():
            conv.is_deleted = True

    def rename(self, user: Account, conversation_id: int, name: str) -> Conversation:
        conv = self.get(user, conversation_id)
        with db.auto_commit():
            conv.title = name
        return conv

    def update_is_pinned(self, user: Account, conversation_id: int, is_pinned: bool) -> Conversation:
        conv = self.get(user, conversation_id)
        with db.auto_commit():
            conv.is_pinned = is_pinned
        return conv

    def get_name(self, user: Account, conversation_id: int) -> str:
        return self.get(user, conversation_id).title

    def get_summary(self, user: Account, conversation_id: int) -> str:
        return self.get(user, conversation_id).summary or ""

    def update_summary(self, user: Account, conversation_id: int, summary: str) -> None:
        conv = self.get(user, conversation_id)
        with db.auto_commit():
            conv.summary = summary

    def get_or_create_for_app(self, user: Account, app: App) -> Conversation:
        """该 user × app 下最近一条未删除会话；无则创建。
        用于 debug_chat（编排预览，读草稿配置）在 conversation_id 缺省时拿默认会话。
        排除 invoke_from='published' 的会话——那是「与已发布应用对话」的独立 silo，不与调试混用。"""
        stmt = (
            select(Conversation)
            .where(
                Conversation.app_id == app.id,
                Conversation.user_id == user.id,
                Conversation.is_deleted.is_(False),
                Conversation.invoke_from != InvokeFrom.PUBLISHED.value,
            )
            .order_by(desc(Conversation.updated_at))
            .limit(1)
        )
        conv = db.session.scalars(stmt).first()
        if conv is not None:
            return conv
        return self.create(user, app)

    def get_or_create_published_for_app(self, user: Account, app: App) -> Conversation:
        """该 user × app 下「与已发布应用对话」的最近一条未删除会话（invoke_from='published'）；无则创建。
        与调试会话隔离，保证已发布对话只走已发布配置、历史不与编排预览相混。"""
        stmt = (
            select(Conversation)
            .where(
                Conversation.app_id == app.id,
                Conversation.user_id == user.id,
                Conversation.is_deleted.is_(False),
                Conversation.invoke_from == InvokeFrom.PUBLISHED.value,
            )
            .order_by(desc(Conversation.updated_at))
            .limit(1)
        )
        conv = db.session.scalars(stmt).first()
        if conv is not None:
            return conv
        return self.create(user, app, title="已发布应用对话", invoke_from=InvokeFrom.PUBLISHED.value)

    def clear_published_messages(self, user: Account, app: App) -> None:
        """软删该 user × app「已发布对话」silo 的全部消息，但保留会话行与其 summary。
        用于已发布对话弹窗的「清空历史」——只抹聊天记录，长期记忆（summary）原样保留。"""
        conv = self.get_or_create_published_for_app(user, app)
        with db.auto_commit():
            db.session.query(Message).filter(
                Message.conversation_id == conv.id,
                Message.is_deleted.is_(False),
            ).update({Message.is_deleted: True}, synchronize_session=False)

    # ---------- messages ----------

    def list_messages_with_page(
        self, user: Account, conversation_id: int, req: GetMessagesWithPageReq,
    ) -> PageModel:
        """游标分页（created_at < 游标）+ 普通分页。list 内每项是 MessageItem 的 dict（已 model_dump）。"""
        conv = self.get(user, conversation_id)
        base = (
            select(Message)
            .where(Message.conversation_id == conv.id, Message.is_deleted.is_(False))
        )
        if req.created_at > 0:
            base = base.where(Message.created_at < datetime.utcfromtimestamp(req.created_at))

        count_stmt = select(func.count()).select_from(base.subquery())
        total_record = int(db.session.scalar(count_stmt) or 0)
        paginator = Paginator(page=req.current_page, page_size=req.page_size, total_record=total_record)

        page_stmt = (
            base.order_by(Message.created_at.desc())
            .offset(paginator.offset)
            .limit(req.page_size)
        )
        rows = list(db.session.scalars(page_stmt))

        items = [
            MessageItem.model_validate(_message_view(m)).model_dump(mode="json")
            for m in rows
        ]
        return PageModel(list=items, paginator=paginator.to_dict()["paginator"])

    def delete_message(self, user: Account, conversation_id: int, message_id: int) -> None:
        """软删某会话下的某条消息。message 必须真的挂在该 conversation 下，否则 404，
        避免别处的 message_id 被借此偷删。"""
        conv = self.get(user, conversation_id)
        msg = db.session.get(Message, message_id)
        if msg is None or msg.conversation_id != conv.id or msg.is_deleted:
            raise NotFoundException("消息不存在")
        with db.auto_commit():
            msg.is_deleted = True

    def history_for_llm(
        self, conversation: Conversation, cap_turns: int = HISTORY_TURNS_CAP,
    ) -> list[HistoryTurn]:
        """取最近 cap_turns 行（每行一轮）正常完成的消息，按时间正序拆成
        user / assistant 的 HistoryTurn 序列，用于拼进 LLM 输入。
        user 轮带该轮附件（image_urls / file_infos），由 build_lc_messages 重建多模态；
        排除 is_deleted=True / status != normal / answer 为空的行。cap_turns=0 → 不带历史。"""
        if cap_turns <= 0:
            return []
        stmt = (
            select(Message)
            .where(
                Message.conversation_id == conversation.id,
                Message.is_deleted.is_(False),
                Message.status == "normal",
                Message.answer != "",
            )
            .order_by(Message.created_at.desc())
            .limit(cap_turns)
        )
        recent = list(db.session.scalars(stmt))
        recent.reverse()
        turns: list[HistoryTurn] = []
        for m in recent:
            turns.append(HistoryTurn(
                role="user", content=m.query,
                image_urls=list(m.image_urls or []),
                file_infos=list(getattr(m, "file_infos", None) or []),
            ))
            turns.append(HistoryTurn(role="assistant", content=m.answer))
        return turns

    # ---------- 一轮 = 一行 的写入 ----------

    def append_round(
        self, conversation_id: int, *, app_id: int, user_id: int,
        query: str, image_urls: Optional[list[str]] = None,
        file_infos: Optional[list[dict]] = None, invoke_from: str = "web_app",
        end_user_id: Optional[int] = None,
    ) -> Message:
        """开启一轮：建 ai_message 行（status=normal、answer 留空），返回 Message 实例。
        debug_chat / complete_chat 入口处调，先拿到 message_id 再走 LLM。
        end_user_id 仅开放 API（service_api）传入，站内聊天为 None。"""
        with db.auto_commit():
            msg = Message(
                app_id=app_id,
                conversation_id=conversation_id,
                invoke_from=invoke_from,
                created_by=user_id,
                end_user_id=end_user_id,
                query=query,
                image_urls=image_urls or [],
                file_infos=file_infos or [],
            )
            db.session.add(msg)
            conv = db.session.get(Conversation, conversation_id)
            if conv is not None:
                conv.updated_at = datetime.utcnow()
        db.session.refresh(msg)
        return msg

    def finalize_round(
        self, message_id: int, *, answer: str, provider: Optional[str], model_name: Optional[str],
        latency: float, status: str = "normal", error: str = "",
        input_token_count: int = 0, output_token_count: int = 0,
    ) -> Message:
        """流式/同步结束时回写 answer 与统计。

        token 用量由调用方从 LLM 响应自带的 usage_metadata 采集后传入（缺省 0）；价格在此本地查表算
        （`calculate_price`，无 pricing 配置则全 0），一并写入 8 个 token/price 列。"""
        in_tok = int(input_token_count or 0)
        out_tok = int(output_token_count or 0)
        price = self.llm_manager.calculate_price(provider, model_name, in_tok, out_tok)
        with db.auto_commit():
            msg = db.session.get(Message, message_id)
            if msg is None:
                raise NotFoundException("消息不存在")
            msg.answer = answer
            msg.provider = provider
            msg.model_name = model_name
            msg.latency = latency
            msg.status = status
            msg.error = error
            msg.message_token_count = in_tok
            msg.answer_token_count = out_tok
            msg.total_token_count = in_tok + out_tok
            msg.message_unit_price = price["input_unit_price"]
            msg.answer_unit_price = price["output_unit_price"]
            msg.message_price_unit = price["price_unit"]
            msg.answer_price_unit = price["price_unit"]
            msg.total_price = price["total_price"]
            conv = db.session.get(Conversation, msg.conversation_id)
            if conv is not None:
                conv.updated_at = datetime.utcnow()
        db.session.refresh(msg)
        return msg

    # ---------- 对话后统一收尾钩子：自动命名 + 长期记忆滚动摘要 ----------

    def after_round(
        self, message_id: int, *,
        provider: Optional[str] = None, model: Optional[str] = None,
        long_term_memory_enabled: bool = False,
    ) -> None:
        """对话收尾后的横切逻辑收口（替代此前在各 finalize 点散贴的摘要调用）。

        两个子任务各自自守卫、互不影响，且都绝不影响已收尾的主对话链路：
        ① 会话自动命名——仅当会话标题仍是默认（AUTO_NAME_TITLES）时，据本轮 query 起一个简短标题；
        ② 长期记忆——开启时把本轮问答增量并入会话 summary。"""
        self._maybe_name_conversation(message_id, provider=provider, model=model)
        if long_term_memory_enabled:
            self.update_summary_from_round(message_id, provider=provider, model=model)

    def enqueue_after_round(
        self, message_id: int, *,
        provider: Optional[str] = None, model: Optional[str] = None,
        long_term_memory_enabled: bool = False,
    ) -> None:
        """把对话收尾（自动命名 + 长期记忆摘要）投递到 Celery 异步执行——把这两段 LLM 往返
        从 SSE 收尾路径上摘掉，agent_end 不再等它（首轮 / 开长期记忆时每轮省 0.5~1.5s）。
        任务体最终仍回到本类的 after_round，逻辑与同步路径完全一致。

        投递失败（如 broker 不可用）也绝不影响已收尾的主对话链路：吞掉即可，本轮收尾顶多不发生
        （命名仅首轮一次、摘要要下一轮才被读到，均非主链路依赖）。单测里 after_round_task.delay
        被 monkeypatch 成同请求内同步直调本方法的 after_round，故现有断言行为不变。"""
        try:
            from internal.task.conversation_task import after_round_task

            after_round_task.delay(
                message_id, provider=provider, model=model,
                long_term_memory_enabled=long_term_memory_enabled,
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "投递 after_round 异步任务失败，本轮跳过自动命名/长期记忆摘要", exc_info=True
            )

    def _llm(self, provider: Optional[str], model: Optional[str]):
        """命名/摘要用的 LLM：provider+model 双全时实例化指定模型，否则取环境默认。"""
        if provider and model:
            return self.llm_manager.instantiate(provider, model)
        return self.llm_manager.get_default()

    def generate_conversation_name(
        self, query: str, *, provider: Optional[str] = None, model: Optional[str] = None,
    ) -> str:
        """据用户首句生成简短会话标题；空输入 / 失败一律回 ""。取模型取用方式与摘要一致。"""
        q = (query or "").strip()
        if not q:
            return ""
        try:
            text = extract_text(self._llm(provider, model).invoke(
                build_lc_messages(CONVERSATION_NAME_TEMPLATE, [], q)
            ))
        except Exception:
            return ""
        first_line = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
        title = first_line.strip().strip("\"'“”‘’「」《》").strip()
        return title[:_TITLE_MAX_CHARS]

    def _maybe_name_conversation(
        self, message_id: int, *, provider: Optional[str] = None, model: Optional[str] = None,
    ) -> None:
        """仅当会话标题仍为默认时，用本轮 query 自动命名。非正常完成 / 无答案 / 已删 / 已命名一律跳过。"""
        try:
            msg = db.session.get(Message, message_id)
            if msg is None or msg.is_deleted:
                return
            if msg.status != MessageStatus.NORMAL.value or not (msg.answer or "").strip():
                return
            conv = db.session.get(Conversation, msg.conversation_id)
            if conv is None or conv.is_deleted or conv.title not in AUTO_NAME_TITLES:
                return
            name = self.generate_conversation_name(msg.query, provider=provider, model=model)
            if not name:
                return
            with db.auto_commit():
                conv.title = name
        except Exception:
            db.session.rollback()

    def update_summary_from_round(
        self, message_id: int, *, provider: Optional[str] = None, model: Optional[str] = None,
    ) -> None:
        """把 message_id 这轮问答增量并入所属会话的长期记忆 summary。

        调用方负责判断 long_term_memory.enable（关闭则根本不调）。本方法再自守卫：
        本轮非正常完成 / 无答案 / 会话已删 一律跳过；任何异常都吞掉并回滚，绝不影响已收尾的主链路。
        摘要只在「下一轮」compose_system_prompt 时才被读到，本轮收尾并不依赖它，异步化不影响正确性
        （极快连发时至多延后一轮生效）。"""
        try:
            msg = db.session.get(Message, message_id)
            if msg is None or msg.is_deleted:
                return
            if msg.status != MessageStatus.NORMAL.value or not (msg.answer or "").strip():
                return
            conv = db.session.get(Conversation, msg.conversation_id)
            if conv is None or conv.is_deleted:
                return
            old_summary = conv.summary or ""
            new_lines = f"Human: {msg.query}\nAI: {msg.answer}"
            prompt = SUMMARIZER_TEMPLATE.format(summary=old_summary, new_lines=new_lines)
            new_summary = extract_text(self._llm(provider, model).invoke(
                build_lc_messages("", [], prompt)
            )).strip()
            if not new_summary:
                return
            with db.auto_commit():
                conv.summary = new_summary[:_SUMMARY_MAX_CHARS]
        except Exception:
            db.session.rollback()


def _message_view(m: Message) -> dict:
    """把 Message ORM 实例展开成 MessageItem 字段字典。agent_thoughts 本轮恒空。"""
    return {
        "id": m.id,
        "conversation_id": m.conversation_id,
        "app_id": m.app_id,
        "query": m.query,
        "answer": m.answer,
        "image_urls": m.image_urls or [],
        # 文档附件给前端只回元数据，剥掉 text 抽取缓存（可达 20k 字符，纯后端用）
        "file_infos": [
            {k: fi.get(k) for k in ("url", "name", "extension")}
            for fi in (getattr(m, "file_infos", None) or [])
        ],
        "status": m.status,
        "error": m.error,
        "provider": m.provider,
        "model_name": m.model_name,
        "latency": float(m.latency or 0.0),
        "total_token_count": int(m.total_token_count or 0),
        "total_price": float(m.total_price or 0.0),
        "agent_thoughts": [],
        "created_at": m.created_at,
    }
