from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import Boolean, Column, DateTime, Integer, String

from internal.extension.database_extension import db


class Account(UserMixin, db.Model):
    """自有账号表。替换原本依赖外部网关的 user 体系；无管理员/RBAC 概念。"""
    __tablename__ = "account"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=True)
    avatar = Column(String(1024), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_id(self) -> str:
        return str(self.id)

    def to_dict(self) -> dict:
        return {"id": self.id, "email": self.email, "name": self.name, "avatar": self.avatar}

    # 接缝兼容：无管理员/RBAC，下游 handler 读到的统一是「非管理员、无权限码」。
    # Phase 4 移植 handler 时据此移除 is_admin 守卫、拍平配额。
    @property
    def is_admin(self) -> bool:
        return False

    @property
    def permission_codes(self) -> list:
        return []

    @property
    def role_names(self) -> list:
        return []
