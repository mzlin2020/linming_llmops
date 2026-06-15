"""自有表：ai_upload_file（上传文件登记）。

文件存本地文件系统（STORAGE_ROOT），`key` 为相对存储根的路径。
仅做“登记 + 落盘”，文件解析在 file_extractor 里按 extension 选 loader。
user_id 是普通索引列（= account.id），不加 FK。
"""
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    String,
)

from internal.extension.database_extension import db


class UploadFile(db.Model):
    """上传文件记录：一行 = 一个落盘的文件。"""

    __tablename__ = "ai_upload_file"
    __table_args__ = (
        Index("ix_ai_upload_file_user_id", "user_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, nullable=False, comment="归属账号 id（= account.id）",
    )
    name = Column(String(512), nullable=False, default="", server_default="", comment="原始文件名")
    key = Column(String(512), nullable=False, default="", server_default="", comment="存储相对路径（相对 STORAGE_ROOT）")
    size = Column(Integer, nullable=False, default=0, server_default="0", comment="文件大小(字节)")
    extension = Column(String(64), nullable=False, default="", server_default="", comment="扩展名(小写,不带点)")
    mime_type = Column(String(128), nullable=False, default="", server_default="", comment="MIME 类型")
    hash = Column(String(128), nullable=False, default="", server_default="", comment="内容哈希")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
