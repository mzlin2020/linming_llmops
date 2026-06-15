"""自有表：ai_api_key / ai_end_user（开放 API 用）。所有自有表必须 ai_ 前缀。

- ai_api_key  —— 签发的 API 密钥。一把 key 绑「账号」，不绑单个 app；
                 调用方在请求体里传 app_id，故一把 key 可调该账号名下任意已发布 app。
- ai_end_user —— 开放 API 的终端用户（账号的「用户的用户」）。用于隔离外部调用者的会话。
                 极简形态：只记 租户(user_id) + 所属 app；未传 end_user_id 时自动建匿名一条。

ai_conversation.end_user_id 带 FK→本表（ON DELETE SET NULL，低频表）；
ai_message.end_user_id 走软引用·无 FK（高频表，加 FK 会整表重建撞历史孤儿行）。
user_id 是普通索引列（= account.id），不加 FK。
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)

from internal.extension.database_extension import db


class ApiKey(db.Model):
    __tablename__ = "ai_api_key"
    __table_args__ = (
        Index("ix_ai_api_key_user_id", "user_id"),
        Index("uq_ai_api_key_api_key", "api_key", unique=True),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        nullable=False,
        comment="归属账号 id（钥匙主人；= account.id）",
    )
    api_key = Column(String(255), nullable=False, comment="密钥串(含前缀；明文存，配唯一索引)")
    is_active = Column(
        Boolean, nullable=False, default=True, server_default=text("1"),
        comment="是否启用；停用后立即失效",
    )
    remark = Column(String(255), nullable=False, default="", server_default="", comment="备注")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class EndUser(db.Model):
    __tablename__ = "ai_end_user"
    __table_args__ = (
        Index("ix_ai_end_user_user_id", "user_id"),
        Index("ix_ai_end_user_app_id", "app_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        nullable=False,
        comment="租户=钥匙主人账号 id（= account.id）",
    )
    app_id = Column(
        Integer,
        ForeignKey("ai_app.id", ondelete="CASCADE", name="fk_ai_end_user_app"),
        nullable=False,
        comment="所属 ai_app(终端用户只在某 app 下存在)",
    )

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
