"""应用服务：基础信息 CRUD + 草稿/发布/版本历史/回退。

三表协作：
- create / get_or_create_default / get_or_create_assistant_agent_app：建 App 的同时建一条
  草稿配置行（ai_app_config_version, config_type=draft, version=0），preset/model 写入草稿行。
- update_draft_app_config：原地改草稿行（不产生新行）。
- publish_draft_app_config：草稿快照成 AppConfig 运行配置 + 更新 App 指针/状态 + 追加 published 历史行。
- fallback_history_to_draft：把某 published 历史行字段拷回草稿行。

公共应用商店（ai_public_app）：任意登录用户可把自己「已发布」的应用上架成 sanitize 快照（剥离私有引用），
添加=把公共快照复制回当前用户私有表（app.source_public_app_id 记来源，做「是否已添加」去重）。
不变式「商店条目存在 ⟺ 应用已发布，且内容 = 当前已发布配置」由三处联动维持：
发布就地刷新快照 / 取消发布连带下架 / 删除应用连带下架。
"""
import random
from dataclasses import dataclass
from math import ceil
from typing import Optional

from injector import inject
from sqlalchemy import desc, func, select

from internal.entity import (
    ASSISTANT_AGENT_DEFAULT_TOOLS,
    ASSISTANT_AGENT_PRESET_PROMPT,
    DEFAULT_APP_CONFIG,
    DEFAULT_APP_ICONS,
    AppConfigType,
    AppStatus,
)
from internal.exception import ForbiddenException, NotFoundException, ValidateErrorException
from internal.extension.database_extension import db
from internal.lib.helper import dedupe_copy_name, generate_random_string
from internal.model import Account, App, AppConfig, AppConfigVersion, Conversation, PublicApp
from internal.model.app import CONFIG_FIELDS
from internal.schema.app_schema import AppCreateReq, AppUpdateReq, GetAppStoreWithPageReq
from internal.schema.conversation_schema import PageModel
from internal.service.app_config_service import AppConfigService, serialize_config

_NAME_MAX = 64  # ai_app.name 列上限


def _random_default_icon() -> str:
    """从内置图标里随机挑一个，作为用户未上传图标时的默认头像。"""
    return random.choice(DEFAULT_APP_ICONS)


def _epoch(dt) -> int:
    return int(dt.timestamp()) if dt else 0


def _sanitize_public_config(config: dict) -> dict:
    """上架商店 / 复制公共应用时剥离配置里的私有引用：
    - tools 仅保留 builtin_tool——api_tool 按 id 引用发布者的私有插件，ToolResolver 运行时
      不校验归属，跨用户复制不剥离会让添加者越权调用发布者的私有工具
    - datasets 清空——知识库检索只按 dataset_id 过滤，同理越权
    - workflows 清空——运行时未做，与校验层保持一致
    其余字段原样保留。"""
    cleaned = dict(config or {})
    cleaned["tools"] = [
        t for t in (cleaned.get("tools") or [])
        if isinstance(t, dict) and t.get("type") == "builtin_tool"
    ]
    cleaned["datasets"] = []
    cleaned["workflows"] = []
    return cleaned


def _snapshot_public_app(pub: PublicApp, app: App, app_config: AppConfig) -> None:
    """把 app 的已发布配置拍进公共条目：sanitize 后就地覆盖快照字段（不动 published_by/source_app_id）。
    上架与「重新发布自动同步」共用，保证商店内容恒等于当前已发布配置。"""
    sanitized = _sanitize_public_config(serialize_config(app_config))
    mc = sanitized.get("model_config") or {}
    pub.name = app.name
    pub.description = app.description or ""
    pub.icon = app.icon or ""
    pub.preset_prompt = sanitized.get("preset_prompt") or ""
    pub.app_config = sanitized
    pub.model_provider = str(mc.get("provider") or "")
    pub.model_name = str(mc.get("model") or "")
    pub.tool_count = len(sanitized.get("tools") or [])


def _public_app_brief(pub: PublicApp, added: bool) -> dict:
    """商店列表项：全部取自上架时的冗余快照，零查询渲染。added=当前用户是否已添加过。"""
    return {
        "id": pub.id,
        "name": pub.name,
        "icon": pub.icon,
        "description": pub.description,
        "model_provider": pub.model_provider or "",
        "model_name": pub.model_name or "",
        "tool_count": int(pub.tool_count or 0),
        "added": added,
        "created_at": _epoch(pub.created_at),
    }


@inject
@dataclass
class AppService:
    app_config_service: AppConfigService

    # ---------- 基础 CRUD ----------

    def create(self, user: Account, req: AppCreateReq) -> App:
        preset = req.preset_prompt if req.preset_prompt is not None else None
        return self._create_app_with_draft(
            user_id=user.id, name=req.name,
            description=req.description or "", icon=req.icon or _random_default_icon(),
            preset_prompt=preset,
        )

    def get(self, user: Account, app_id: int) -> App:
        app = db.session.get(App, app_id)
        if not app:
            raise NotFoundException("应用不存在")
        if app.user_id != user.id and not user.is_admin:
            raise ForbiddenException("无权访问该应用")
        return app

    def list_by_user(self, user: Account, include_builtin: bool = False) -> list[App]:
        stmt = select(App).where(App.user_id == user.id).order_by(App.created_at.desc())
        apps = list(db.session.scalars(stmt))
        if include_builtin:
            # 追加全局内置应用（辅助 Agent），只读展示，前端按 is_assistant_agent 禁用编辑/删除
            builtin = list(
                db.session.scalars(
                    select(App).where(App.is_assistant_agent.is_(True)).order_by(App.created_at.asc())
                )
            )
            apps = apps + [a for a in builtin if a not in apps]
        return apps

    def update(self, user: Account, app_id: int, req: AppUpdateReq) -> App:
        app = self.get(user, app_id)
        draft = app.draft_app_config  # 确保草稿行存在（缺失时兜底创建并提交一次）
        with db.auto_commit():
            if req.name is not None:
                app.name = req.name
            if req.description is not None:
                app.description = req.description
            if req.icon is not None:
                app.icon = req.icon
            # 兼容旧端点：基础更新里直接带的 preset/model/dialog 桥接进草稿行
            if req.preset_prompt is not None:
                draft.preset_prompt = req.preset_prompt
            if req.model_config_payload is not None:
                draft.model_config = req.model_config_payload
            if req.dialog_round is not None:
                draft.dialog_round = req.dialog_round
        return app

    def delete(self, user: Account, app_id: int) -> None:
        app = self.get(user, app_id)
        with db.auto_commit():
            # 连带下架其公共条目（若有），避免商店出现孤儿
            db.session.query(PublicApp).filter(PublicApp.source_app_id == app.id).delete()
            db.session.delete(app)

    def copy(self, user: Account, app_id: int) -> App:
        """复制一个应用：建新 app（名带「副本」、未发布、非默认/非内置），草稿配置整体拷自源 app 的草稿行
        （只复制草稿，不带发布历史）。"""
        src = self.get(user, app_id)
        draft = src.draft_app_config
        overrides = {field: getattr(draft, field) for field in CONFIG_FIELDS}
        return self._create_app_with_draft(
            user_id=user.id,
            name=f"{src.name} 副本"[:64],
            description=src.description or "",
            icon=src.icon or _random_default_icon(),
            config_overrides=overrides,
        )

    # ---------- 草稿配置 ----------

    def get_draft_app_config(self, user: Account, app_id: int) -> dict:
        app = self.get(user, app_id)
        return self.app_config_service.get_draft_app_config(app)

    def update_draft_app_config(self, user: Account, app_id: int, payload: dict) -> dict:
        app = self.get(user, app_id)
        cleaned = self.app_config_service.validate_draft_app_config(
            payload, user.id, is_admin=bool(getattr(user, "is_admin", False)),
        )
        draft = app.draft_app_config
        with db.auto_commit():
            for key, value in cleaned.items():
                setattr(draft, key, value)
        return self.app_config_service.get_draft_app_config(app)

    # ---------- 发布 / 取消发布 ----------

    def publish_draft_app_config(self, user: Account, app_id: int) -> App:
        app = self.get(user, app_id)
        draft = app.draft_app_config
        draft_data = {field: getattr(draft, field) for field in CONFIG_FIELDS}
        with db.auto_commit():
            # 1. 草稿快照成新的运行配置
            app_config = AppConfig(app_id=app.id, **draft_data)
            db.session.add(app_config)
            db.session.flush()
            # 2. 更新应用指针 / 状态 / 凭证
            app.app_config_id = app_config.id
            app.status = AppStatus.PUBLISHED.value
            if not app.token:
                app.token = generate_random_string(16)
            # 3. 追加一条 published 历史版本（version = 当前最大 + 1）
            max_version = db.session.query(
                func.coalesce(func.max(AppConfigVersion.version), 0)
            ).filter(
                AppConfigVersion.app_id == app.id,
                AppConfigVersion.config_type == AppConfigType.PUBLISHED.value,
            ).scalar()
            history = AppConfigVersion(
                app_id=app.id,
                version=int(max_version) + 1,
                config_type=AppConfigType.PUBLISHED.value,
                **draft_data,
            )
            db.session.add(history)
            # 4. 商店联动：若该应用已上架，就地刷新公共快照（商店内容恒等于当前已发布配置）
            pub = db.session.query(PublicApp).filter(PublicApp.source_app_id == app.id).one_or_none()
            if pub is not None:
                _snapshot_public_app(pub, app, app_config)
        db.session.refresh(app)
        return app

    def cancel_publish_app_config(self, user: Account, app_id: int) -> App:
        app = self.get(user, app_id)
        if app.status != AppStatus.PUBLISHED.value:
            raise ValidateErrorException(message="当前应用未发布，无需取消")
        with db.auto_commit():
            app.status = AppStatus.DRAFT.value
            app.app_config_id = None
            app.token = None
            # 商店联动：取消发布连带下架（商店条目存在 ⟺ 应用已发布）
            db.session.query(PublicApp).filter(PublicApp.source_app_id == app.id).delete()
        db.session.refresh(app)
        return app

    # ---------- 版本历史 / 回退 ----------

    def get_publish_histories_with_page(
        self, user: Account, app_id: int, current_page: int, page_size: int,
    ) -> PageModel:
        app = self.get(user, app_id)
        base = select(AppConfigVersion).where(
            AppConfigVersion.app_id == app.id,
            AppConfigVersion.config_type == AppConfigType.PUBLISHED.value,
        )
        total_record = int(db.session.scalar(select(func.count()).select_from(base.subquery())) or 0)
        total_page = ceil(total_record / page_size) if total_record else 0
        rows = list(
            db.session.scalars(
                base.order_by(desc(AppConfigVersion.version))
                .offset((current_page - 1) * page_size)
                .limit(page_size)
            )
        )
        items = [
            {
                "id": r.id,
                "version": r.version,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
        return PageModel(
            list=items,
            paginator={
                "current_page": current_page,
                "page_size": page_size,
                "total_page": total_page,
                "total_record": total_record,
            },
        )

    def fallback_history_to_draft(self, user: Account, app_id: int, app_config_version_id: int) -> dict:
        app = self.get(user, app_id)
        version = db.session.get(AppConfigVersion, app_config_version_id)
        if (
            version is None
            or version.app_id != app.id
            or version.config_type != AppConfigType.PUBLISHED.value
        ):
            raise NotFoundException("该历史版本配置不存在")
        draft = app.draft_app_config
        data = {field: getattr(version, field) for field in CONFIG_FIELDS}
        with db.auto_commit():
            for key, value in data.items():
                setattr(draft, key, value)
        return self.app_config_service.get_draft_app_config(app)

    def get_published_config(self, user: Account, app_id: int) -> Optional[dict]:
        app = self.get(user, app_id)
        return self.app_config_service.get_published_config(app)

    # ---------- 公共应用商店 ----------

    def get_app_store_with_page(self, req: GetAppStoreWithPageReq, user: Account) -> dict:
        """商店列表：所有已上架公共应用分页（sort 优先、再按上架时间倒序），附「是否已添加」标记。"""
        query = db.session.query(PublicApp)
        if req.search_word:
            query = query.filter(PublicApp.name.like(f"%{req.search_word}%"))
        total_record = query.count()
        total_page = ceil(total_record / req.page_size) if total_record else 0
        rows = (
            query.order_by(desc(PublicApp.sort), desc(PublicApp.created_at))
            .offset((req.current_page - 1) * req.page_size)
            .limit(req.page_size)
            .all()
        )
        added_ids = self._added_public_app_ids(user.id, [p.id for p in rows])
        return {
            "list": [_public_app_brief(p, p.id in added_ids) for p in rows],
            "paginator": {
                "current_page": req.current_page,
                "page_size": req.page_size,
                "total_page": total_page,
                "total_record": total_record,
            },
        }

    def set_app_public(self, app_id: int, is_public: bool, user: Account) -> None:
        """上架 / 下架公共应用商店：任意登录用户，但只能操作自己的应用；上架要求应用已发布。
        上架=对当前已发布配置拍 sanitize 快照（upsert）；下架=删除公共条目。"""
        app = db.session.get(App, app_id)
        # 上架语义必须限「自己的应用」——越权一律 404（不泄露存在性）
        if app is None or app.user_id != user.id:
            raise NotFoundException("应用不存在")
        existing = db.session.query(PublicApp).filter(
            PublicApp.source_app_id == app.id
        ).one_or_none()
        if not is_public:
            if existing is not None:
                with db.auto_commit():
                    db.session.delete(existing)
            return
        published = app.app_config
        if app.status != AppStatus.PUBLISHED.value or published is None:
            raise ValidateErrorException(message="请先发布应用，再上架到商店")
        # 先算好全部快照字段再 add()，避免 autoflush 把半空行（published_by=NULL）抢先 INSERT
        with db.auto_commit():
            if existing is None:
                existing = PublicApp(source_app_id=app.id, published_by=user.id)
                _snapshot_public_app(existing, app, published)
                db.session.add(existing)
            else:
                _snapshot_public_app(existing, app, published)
                existing.published_by = user.id

    def add_app_to_me(self, public_id: int, user: Account) -> App:
        """把一条公共应用复制成当前用户的私有应用（草稿态、非默认，含 sanitize 后的完整配置）。"""
        pub = db.session.get(PublicApp, public_id)
        if pub is None:
            raise NotFoundException("该公共应用不存在")
        dup = db.session.query(App.id).filter(
            App.user_id == user.id,
            App.source_public_app_id == pub.id,
        ).first()
        if dup is not None:
            raise ValidateErrorException(message="你已添加过该应用")
        name = self._dedupe_app_name(pub.name, user.id)
        # 快照本就已 sanitize，这里再剥一遍作双保险（config_overrides 直接展开入库、不过校验）
        overrides = _sanitize_public_config(dict(pub.app_config or {}))
        app = self._create_app_with_draft(
            user_id=user.id,
            name=name,
            description=pub.description or "",
            icon=pub.icon or _random_default_icon(),
            config_overrides=overrides,
        )
        with db.auto_commit():
            app.source_public_app_id = pub.id
        return app

    def is_app_public(self, app_id: int) -> bool:
        """该应用当前是否已上架商店（GET /apps/<id> 详情回显编排页开关用）。"""
        return db.session.query(PublicApp.id).filter(
            PublicApp.source_app_id == app_id
        ).first() is not None

    # ---------- 默认 App（"每位用户进入即聊"的兜底） ----------

    def get_or_create_default(self, user: Account) -> App:
        """按 (user_id, is_default=True) 查；不存在则自动创建一个 name='默认助手' 的 App（含草稿配置）。"""
        stmt = (
            select(App)
            .where(App.user_id == user.id, App.is_default.is_(True))
            .order_by(App.created_at.asc())
            .limit(1)
        )
        app = db.session.scalars(stmt).first()
        if app is not None:
            return app
        return self._create_app_with_draft(
            user_id=user.id, name="默认助手", description="", icon=_random_default_icon(),
            is_default=True,
        )

    # ---------- 全局辅助 Agent App（所有用户共享同一人设的内置 app） ----------

    def get_or_create_assistant_agent_app(self) -> App:
        """全局唯一的辅助 Agent 内置 app（user_id 为 NULL，所有登录用户共享）。
        人设与默认工具均以代码为准：已存内置 app 的草稿 preset / tools 与当前常量漂移时就地同步草稿行，
        改 ASSISTANT_AGENT_PRESET_PROMPT 或 ASSISTANT_AGENT_DEFAULT_TOOLS 后无需删表重建即可生效，
        也不动会话/消息数据。辅助 Agent 链路只用此方法拿 app，绝不走 get()（会因 user_id 不匹配报 403）。"""
        stmt = (
            select(App)
            .where(App.is_assistant_agent.is_(True))
            .order_by(App.created_at.asc())
            .limit(1)
        )
        app = db.session.scalars(stmt).first()
        if app is not None:
            draft = app.draft_app_config
            preset_drift = draft.preset_prompt != ASSISTANT_AGENT_PRESET_PROMPT
            tools_drift = draft.tools != ASSISTANT_AGENT_DEFAULT_TOOLS
            if preset_drift or tools_drift:
                with db.auto_commit():
                    if preset_drift:
                        draft.preset_prompt = ASSISTANT_AGENT_PRESET_PROMPT
                    if tools_drift:
                        draft.tools = ASSISTANT_AGENT_DEFAULT_TOOLS
            return app
        return self._create_app_with_draft(
            user_id=None, name="AI 助手", description="平台内置 AI 助手", icon="",
            is_assistant_agent=True, preset_prompt=ASSISTANT_AGENT_PRESET_PROMPT,
            config_overrides={"tools": ASSISTANT_AGENT_DEFAULT_TOOLS},
        )

    # ---------- 长期记忆 ----------

    def _latest_active_conversation(self, user: Account, app: App) -> Optional[Conversation]:
        stmt = (
            select(Conversation)
            .where(
                Conversation.app_id == app.id,
                Conversation.user_id == user.id,
                Conversation.is_deleted.is_(False),
            )
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        return db.session.scalars(stmt).first()

    def get_summary(self, user: Account, app_id: int) -> str:
        app = self.get(user, app_id)
        conv = self._latest_active_conversation(user, app)
        if conv is None:
            return ""
        return conv.summary or ""

    def update_summary(self, user: Account, app_id: int, summary: str) -> None:
        app = self.get(user, app_id)
        conv = self._latest_active_conversation(user, app)
        if conv is None:
            with db.auto_commit():
                conv = Conversation(
                    app_id=app.id,
                    user_id=user.id,
                    title="新会话",
                    invoke_from="web_app",
                    created_by=user.id,
                    summary=summary,
                )
                db.session.add(conv)
            return
        with db.auto_commit():
            conv.summary = summary

    def delete_debug_conversation(self, user: Account, app_id: int) -> None:
        app = self.get(user, app_id)
        with db.auto_commit():
            db.session.query(Conversation).filter(
                Conversation.app_id == app.id,
                Conversation.user_id == user.id,
                Conversation.is_deleted.is_(False),
            ).update({Conversation.is_deleted: True}, synchronize_session=False)

    # ---------- internal ----------

    def _added_public_app_ids(self, user_id: int, public_ids: list) -> set:
        """这些公共应用中，当前用户已添加过哪些（基于私有 app.source_public_app_id）。"""
        if not public_ids:
            return set()
        return {
            row[0]
            for row in db.session.query(App.source_public_app_id)
            .filter(App.user_id == user_id, App.source_public_app_id.in_(public_ids))
            .all()
        }

    def _dedupe_app_name(self, base: str, user_id: int) -> str:
        """在该用户下算出不与现有应用重名的名字（应用名无唯一约束，加后缀纯为 UX，与插件商店一致）。"""
        existing = {
            row[0]
            for row in db.session.query(App.name).filter(App.user_id == user_id).all()
        }
        return dedupe_copy_name(base, existing, _NAME_MAX)

    def _create_app_with_draft(
        self, *, user_id: Optional[int], name: str, description: str = "", icon: str = "",
        is_default: bool = False, is_assistant_agent: bool = False,
        preset_prompt: Optional[str] = None, config_overrides: Optional[dict] = None,
    ) -> App:
        """建 App + 一条草稿配置行（config_type=draft, version=0），回填 draft_app_config_id。
        config_overrides 不为空时（如复制应用）覆盖默认草稿字段，把源 app 的 14 字段整体带过来。"""
        draft_cfg = dict(DEFAULT_APP_CONFIG)
        if config_overrides:
            draft_cfg.update({k: v for k, v in config_overrides.items() if k in DEFAULT_APP_CONFIG})
        if preset_prompt is not None:
            draft_cfg["preset_prompt"] = preset_prompt
        with db.auto_commit():
            app = App(
                user_id=user_id,
                name=name,
                description=description,
                icon=icon,
                is_default=is_default,
                is_assistant_agent=is_assistant_agent,
                status=AppStatus.DRAFT.value,
            )
            db.session.add(app)
            db.session.flush()
            draft = AppConfigVersion(
                app_id=app.id,
                version=0,
                config_type=AppConfigType.DRAFT.value,
                **draft_cfg,
            )
            db.session.add(draft)
            db.session.flush()
            app.draft_app_config_id = draft.id
        db.session.refresh(app)
        return app
