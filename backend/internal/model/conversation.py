"""自有表：ai_conversation / ai_message。

会话与消息分离：一个 conversation 挂多条 message。一条 ai_message 代表“一轮”
（user 提问 query + assistant 回答 answer），不再是“一条消息一行”。
删除走软删（is_deleted=True），DB 物理行不动。

Conversation 删了会级联清 Message；Message 删了会级联清 MessageAgentThought（链式）。
user_id / created_by 是普通索引列（= account.id），不加 FK、不级联。
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import relationship

from internal.extension.database_extension import db


class Conversation(db.Model):
    __tablename__ = "ai_conversation"
    __table_args__ = (
        Index("ix_ai_conversation_app_id", "app_id"),
        Index("ix_ai_conversation_user_id_updated_at", "user_id", "updated_at"),
        Index(
            "ix_ai_conversation_user_app_pinned_updated",
            "user_id", "app_id", "is_pinned", "updated_at",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id = Column(
        Integer,
        ForeignKey("ai_app.id", ondelete="CASCADE", name="fk_ai_conversation_app"),
        nullable=False,
        comment="所属 ai_app",
    )
    user_id = Column(
        Integer,
        nullable=False,
        comment="归属账号 id（= account.id）",
    )
    title = Column(String(128), nullable=False, default="新会话", server_default="新会话", comment="会话标题")

    invoke_from = Column(
        String(32), nullable=False, default="web_app", server_default="web_app",
        comment="调用入口；对齐 InvokeFrom 枚举",
    )
    created_by = Column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="创建者账号 id；本轮 = user_id",
    )
    end_user_id = Column(
        Integer,
        ForeignKey("ai_end_user.id", ondelete="SET NULL", name="fk_ai_conversation_end_user"),
        nullable=True,
        comment="终端用户 id（仅开放 API service_api 会话有值；站内会话为 NULL）",
    )
    summary = Column(Text, nullable=True, comment="长期记忆摘要")
    is_pinned = Column(
        Boolean, nullable=False, default=False, server_default=text("0"),
        comment="是否置顶",
    )
    is_deleted = Column(
        Boolean, nullable=False, default=False, server_default=text("0"),
        comment="软删标记",
    )

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship(
        "Message",
        backref="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Message(db.Model):
    __tablename__ = "ai_message"
    __table_args__ = (
        Index("ix_ai_message_conversation_id_created_at", "conversation_id", "created_at"),
        Index("ix_ai_message_app_id", "app_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id = Column(
        Integer,
        ForeignKey("ai_app.id", ondelete="CASCADE", name="fk_ai_message_app"),
        nullable=False,
        comment="所属 ai_app",
    )
    conversation_id = Column(
        Integer,
        ForeignKey("ai_conversation.id", ondelete="CASCADE", name="fk_ai_message_conversation"),
        nullable=False,
        comment="所属会话",
    )
    invoke_from = Column(
        String(32), nullable=False, default="web_app", server_default="web_app",
        comment="调用入口；对齐 InvokeFrom 枚举",
    )
    created_by = Column(
        Integer,
        nullable=False,
        comment="创建者账号 id；本轮 = user_id",
    )
    # 软引用（无 FK，见迁移说明）：高频表加 FK 会整表重建并撞历史孤儿行
    end_user_id = Column(
        Integer,
        nullable=True,
        comment="终端用户 id（软引用；仅开放 API service_api 消息有值，站内消息为 NULL）",
    )

    # 功能字段：一行 = 一轮
    query = Column(Text, nullable=False, default="", server_default="", comment="用户提问")
    answer = Column(Text, nullable=False, default="", server_default="", comment="AI 回答全文")

    # 多模态附件 / LLM 输入序列
    image_urls = Column(JSON, nullable=False, default=list, server_default=text("('[]')"), comment="图片附件 URL 列表")
    # nullable + 无表达式默认：高频存量表加 DEFAULT JSON 列会整表重建撞 FK 孤儿行，
    # 旧行 NULL，读取侧一律 `or []` 兜底；新行由 Python default=list 写 []
    file_infos = Column(
        JSON, nullable=True, default=list,
        comment="文档附件 [{url,name,extension,text}]（text 为截断后抽取缓存；旧行 NULL=[]）",
    )
    message = Column(JSON, nullable=False, default=list, server_default=text("('[]')"), comment="预留：LLM 实际输入消息序列")

    provider = Column(String(64), nullable=True, comment="LLM provider")
    model_name = Column(String(64), nullable=True, comment="LLM model")

    latency = Column(Float, nullable=False, default=0.0, server_default=text("0"), comment="总耗时(秒)")
    status = Column(
        String(32), nullable=False, default="normal", server_default="normal",
        comment="对齐 MessageStatus 枚举: normal/stop/timeout/error",
    )
    error = Column(Text, nullable=False, default="", server_default="", comment="异常信息")

    # 预留：token & 价格统计
    message_token_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    message_unit_price = Column(Numeric(10, 7), nullable=False, default=0, server_default=text("0"))
    message_price_unit = Column(Numeric(10, 4), nullable=False, default=0, server_default=text("0"))
    answer_token_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    answer_unit_price = Column(Numeric(10, 7), nullable=False, default=0, server_default=text("0"))
    answer_price_unit = Column(Numeric(10, 4), nullable=False, default=0, server_default=text("0"))
    total_token_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    total_price = Column(Numeric(10, 7), nullable=False, default=0, server_default=text("0"))

    is_deleted = Column(Boolean, nullable=False, default=False, server_default=text("0"), comment="软删标记")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    agent_thoughts = relationship(
        "MessageAgentThought",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="MessageAgentThought.position",
    )
