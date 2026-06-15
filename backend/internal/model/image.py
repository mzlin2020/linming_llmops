"""自有表：ai_image（AI 生成图片登记，文生图 / 图生图）。

本表只存最终图片 url + 元数据。按 user_id 归属；创建权限由 service 层控制（Phase 4 接入）。
user_id 是普通索引列（= account.id），不加 FK。
"""
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)

from internal.extension.database_extension import db


class AiImage(db.Model):
    """一行 = 一次成功的图像生成记录。"""

    __tablename__ = "ai_image"
    __table_args__ = (
        Index("ix_ai_image_user_id", "user_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, nullable=False, comment="归属账号 id（= account.id）",
    )
    type = Column(String(32), nullable=False, default="text2img", server_default="text2img",
                  comment="生成类型：text2img / img2img")
    provider = Column(String(64), nullable=False, default="", server_default="", comment="模型 provider")
    model = Column(String(128), nullable=False, default="", server_default="", comment="模型名")
    prompt = Column(Text, nullable=False, comment="提示词")
    size = Column(String(32), nullable=False, default="", server_default="", comment="尺寸，如 1024x1024")
    input_image_url = Column(String(1024), nullable=False, default="", server_default="",
                             comment="图生图输入参考图 URL（文生图为空）")
    url = Column(String(1024), nullable=False, default="", server_default="", comment="生成图公网 URL")
    mime_type = Column(String(128), nullable=False, default="", server_default="", comment="MIME 类型")
    size_bytes = Column(Integer, nullable=False, default=0, server_default="0", comment="文件大小(字节)")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
