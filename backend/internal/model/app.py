"""自有表：ai_app / ai_app_config / ai_app_config_version + ai_public_app（公共应用商店）。所有自有表 ai_ 前缀。

三表结构（JSON 存配置、不做 AppDatasetJoin）：
- ai_app                 —— 应用基础信息 + 指针（status / app_config_id / draft_app_config_id）
- ai_app_config          —— 已发布的运行时配置快照（发布时新建，web_app 对话读它）
- ai_app_config_version  —— 草稿（config_type=draft, version=0，原地改）+ 历次发布历史（config_type=published, version 递增）
- ai_public_app          —— 公共应用商店：把「已发布」的应用上架成的自包含快照，全员可读、可一键复制

14 个配置字段（model_config / dialog_round / preset_prompt / tools / workflows / datasets /
retrieval_config / long_term_memory / opening_statement / opening_questions / speech_to_text /
text_to_speech / suggested_after_answer / review_config）统一住在两张配置表。
两表的这 14 列特意保持逐字一致（直接两份），改一处务必同步另一处。
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    text,
)

from internal.entity.app_entity import AppConfigType, DEFAULT_APP_CONFIG
from internal.extension.database_extension import db

# 两张配置表共享、且 finalize/转换逻辑会遍历的 14 个配置字段名。
CONFIG_FIELDS = (
    "model_config", "dialog_round", "preset_prompt", "tools", "workflows", "datasets",
    "retrieval_config", "long_term_memory", "opening_statement", "opening_questions",
    "speech_to_text", "text_to_speech", "suggested_after_answer", "review_config",
)


class App(db.Model):
    __tablename__ = "ai_app"
    __table_args__ = (
        Index("ix_ai_app_user_id", "user_id"),
        Index("ix_ai_app_user_id_is_default", "user_id", "is_default"),
        Index("ix_ai_app_is_assistant_agent", "is_assistant_agent"),
        Index("ix_ai_app_source_public_app_id", "source_public_app_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, nullable=True,
        comment="归属账号 id（= account.id，应用层按 current_user.id 过滤）；全局辅助 Agent 内置 app 为 NULL",
    )
    name = Column(String(64), nullable=False, comment="应用名")
    description = Column(String(512), nullable=False, default="", server_default="", comment="应用描述")
    icon = Column(String(512), nullable=False, default="", server_default="", comment="图标 URL")

    is_default = Column(
        Boolean, nullable=False, default=False, server_default=text("0"),
        comment="当前用户的默认 app；get_or_create_default 使用",
    )
    is_assistant_agent = Column(
        Boolean, nullable=False, default=False, server_default=text("0"),
        comment="全局辅助 Agent 内置 app 标记（user_id 为 NULL，所有用户共享）",
    )

    # ---------- 版本化指针 ----------
    status = Column(
        String(32), nullable=False, default="draft", server_default="draft",
        comment="应用状态：draft / published（对齐 AppStatus）",
    )
    app_config_id = Column(
        Integer, nullable=True,
        comment="已发布运行配置 id（→ai_app_config）；为空代表未发布",
    )
    draft_app_config_id = Column(
        Integer, nullable=True,
        comment="草稿配置 id（→ai_app_config_version 中 config_type=draft 的那条）",
    )
    debug_conversation_id = Column(
        Integer, nullable=True,
        comment="保留：调试会话 id（本轮调试链路仍走 get_or_create_for_app，不读此列）",
    )
    token = Column(String(32), nullable=True, comment="保留：已发布应用访问凭证（未来 WebApp 免登录用）")
    source_public_app_id = Column(
        Integer, nullable=True,
        comment="从哪条公共应用复制来（ai_public_app.id，软引用）；自建应用恒空。用于商店「是否已添加」去重",
    )

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def draft_app_config(self) -> "AppConfigVersion":
        """当前草稿配置行（config_type=draft）。缺失则按 DEFAULT_APP_CONFIG 建一条并回填指针。
        读时兜底创建，迁移后正常路径不会触发。"""
        record = db.session.query(AppConfigVersion).filter(
            AppConfigVersion.app_id == self.id,
            AppConfigVersion.config_type == AppConfigType.DRAFT.value,
        ).order_by(AppConfigVersion.id.asc()).first()
        if record is None:
            record = AppConfigVersion(
                app_id=self.id,
                version=0,
                config_type=AppConfigType.DRAFT.value,
                **DEFAULT_APP_CONFIG,
            )
            db.session.add(record)
            db.session.flush()
            self.draft_app_config_id = record.id
            db.session.commit()
        return record

    @property
    def app_config(self):
        """当前已发布的运行配置；未发布时为 None。web_app 对话读它。"""
        if not self.app_config_id:
            return None
        return db.session.get(AppConfig, self.app_config_id)


class AppConfig(db.Model):
    """已发布的运行时配置快照（一条 = 一次发布的当前生效配置）。"""

    __tablename__ = "ai_app_config"
    __table_args__ = (Index("ix_ai_app_config_app_id", "app_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id = Column(
        Integer,
        ForeignKey("ai_app.id", ondelete="CASCADE", name="fk_ai_app_config_app"),
        nullable=False, comment="所属 ai_app",
    )

    # ----- 14 个配置列（与 AppConfigVersion 保持逐字一致）-----
    model_config = Column(JSON, nullable=False, default=dict, server_default=text("('{}')"), comment="{provider, model, parameters}")
    dialog_round = Column(Integer, nullable=False, default=3, server_default=text("3"), comment="上下文携带轮数")
    preset_prompt = Column(Text, nullable=False, default="", server_default="", comment="系统提示词 / AI 人设")
    tools = Column(JSON, nullable=False, default=list, server_default=text("('[]')"), comment="保留：工具列表")
    workflows = Column(JSON, nullable=False, default=list, server_default=text("('[]')"), comment="保留：工作流列表")
    datasets = Column(JSON, nullable=False, default=list, server_default=text("('[]')"), comment="保留：知识库列表")
    retrieval_config = Column(JSON, nullable=False, default=dict, server_default=text("('{}')"), comment="保留：检索配置")
    long_term_memory = Column(JSON, nullable=False, default=lambda: {"enable": False}, server_default=text("""('{"enable": false}')"""), comment="长期记忆配置")
    opening_statement = Column(Text, nullable=False, default="", server_default="", comment="开场白")
    opening_questions = Column(JSON, nullable=False, default=list, server_default=text("('[]')"), comment="开场建议问题")
    speech_to_text = Column(JSON, nullable=False, default=lambda: {"enable": False}, server_default=text("""('{"enable": false}')"""), comment="保留：语音转文本")
    text_to_speech = Column(JSON, nullable=False, default=lambda: {"enable": False}, server_default=text("""('{"enable": false}')"""), comment="保留：文本转语音")
    suggested_after_answer = Column(JSON, nullable=False, default=lambda: {"enable": True}, server_default=text("""('{"enable": true}')"""), comment="答后建议")
    review_config = Column(JSON, nullable=False, default=dict, server_default=text("('{}')"), comment="保留：审核配置")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class AppConfigVersion(db.Model):
    """应用配置版本表：草稿（config_type=draft, version=0，原地改）+ 历次发布历史。"""

    __tablename__ = "ai_app_config_version"
    __table_args__ = (
        Index("ix_ai_app_config_version_app_id", "app_id"),
        Index("ix_ai_app_config_version_app_id_config_type", "app_id", "config_type"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id = Column(
        Integer,
        ForeignKey("ai_app.id", ondelete="CASCADE", name="fk_ai_app_config_version_app"),
        nullable=False, comment="所属 ai_app",
    )

    # ----- 14 个配置列（与 AppConfig 保持逐字一致）-----
    model_config = Column(JSON, nullable=False, default=dict, server_default=text("('{}')"), comment="{provider, model, parameters}")
    dialog_round = Column(Integer, nullable=False, default=3, server_default=text("3"), comment="上下文携带轮数")
    preset_prompt = Column(Text, nullable=False, default="", server_default="", comment="系统提示词 / AI 人设")
    tools = Column(JSON, nullable=False, default=list, server_default=text("('[]')"), comment="保留：工具列表")
    workflows = Column(JSON, nullable=False, default=list, server_default=text("('[]')"), comment="保留：工作流列表")
    datasets = Column(JSON, nullable=False, default=list, server_default=text("('[]')"), comment="保留：知识库列表")
    retrieval_config = Column(JSON, nullable=False, default=dict, server_default=text("('{}')"), comment="保留：检索配置")
    long_term_memory = Column(JSON, nullable=False, default=lambda: {"enable": False}, server_default=text("""('{"enable": false}')"""), comment="长期记忆配置")
    opening_statement = Column(Text, nullable=False, default="", server_default="", comment="开场白")
    opening_questions = Column(JSON, nullable=False, default=list, server_default=text("('[]')"), comment="开场建议问题")
    speech_to_text = Column(JSON, nullable=False, default=lambda: {"enable": False}, server_default=text("""('{"enable": false}')"""), comment="保留：语音转文本")
    text_to_speech = Column(JSON, nullable=False, default=lambda: {"enable": False}, server_default=text("""('{"enable": false}')"""), comment="保留：文本转语音")
    suggested_after_answer = Column(JSON, nullable=False, default=lambda: {"enable": True}, server_default=text("""('{"enable": true}')"""), comment="答后建议")
    review_config = Column(JSON, nullable=False, default=dict, server_default=text("('{}')"), comment="保留：审核配置")

    version = Column(Integer, nullable=False, default=0, server_default=text("0"), comment="发布版本号；草稿为 0")
    config_type = Column(
        String(32), nullable=False, default="draft", server_default="draft",
        comment="配置类型：draft / published（对齐 AppConfigType）",
    )

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class PublicApp(db.Model):
    """公共应用商店条目：把「已发布」的应用上架成的自包含快照。

    自包含 = 复制 name/description/icon/preset_prompt + 一份 sanitize 后的 14 字段完整配置
    （app_config：tools 仅留 builtin_tool、datasets/workflows 清空——剥离私有引用防越权），
    并冗余 model_provider / model_name / tool_count 三个展示字段，商店列表零查询渲染卡片。
    维持不变式「商店条目存在 ⟺ 应用已发布，且内容 = 当前已发布配置」：
    发布草稿配置就地刷新快照、取消发布 / 删除应用连带下架。
    source_app_id 唯一：一条私有 app 至多对应一条公共条目（上架 upsert / 下架 / 连带下架定位）。
    """

    __tablename__ = "ai_public_app"
    __table_args__ = (
        Index("uq_ai_public_app_source_app_id", "source_app_id", unique=True),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False, default="", server_default="", comment="应用名快照")
    description = Column(String(512), nullable=False, default="", server_default="", comment="应用描述快照")
    icon = Column(String(512), nullable=False, default="", server_default="", comment="图标 URL 快照")
    preset_prompt = Column(Text, nullable=False, default="", server_default="", comment="人设快照（冗余自 app_config，便于卡片展示）")
    app_config = Column(
        JSON, nullable=False, default=dict, server_default=text("('{}')"),
        comment="sanitize 后的 14 字段完整配置（添加时直接喂建应用流程的 config_overrides）",
    )
    model_provider = Column(String(64), nullable=False, default="", server_default="", comment="展示快照：模型 provider")
    model_name = Column(String(128), nullable=False, default="", server_default="", comment="展示快照：模型名")
    tool_count = Column(Integer, nullable=False, default=0, server_default=text("0"), comment="展示快照：内置工具数")
    category = Column(String(32), nullable=False, default="", server_default="", comment="分类（预留，先空）")
    sort = Column(Integer, nullable=False, default=0, server_default=text("0"), comment="排序权重，大在前")
    published_by = Column(
        Integer, nullable=False, comment="发布者账号 id（= account.id）",
    )
    source_app_id = Column(Integer, nullable=False, comment="来源私有 app id（软引用，无 FK）")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
