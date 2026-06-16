"""开放 API 密钥服务。

key 绑「账号」(account) 不绑单个 app——一把 key 可调该账号名下任意已发布 app（app_id 在请求体传）。
明文存 + 唯一索引，按串等值查（将来要哈希再说）。CRUD 一律带 user_id 归属校验，越权抛异常。
前缀由 API_KEY_PREFIX 配置（env 可调，中性默认），不硬编码厂商/项目串。
"""
import secrets
from dataclasses import dataclass
from typing import Optional

from flask import current_app
from injector import inject
from sqlalchemy import desc, select

from internal.exception import ForbiddenException, NotFoundException
from internal.extension.database_extension import db
from internal.model import Account, ApiKey


@inject
@dataclass
class ApiKeyService:
    """开放 API 密钥的签发与管理。"""

    @staticmethod
    def generate_api_key(prefix: Optional[str] = None) -> str:
        """生成带前缀的密钥串：前缀 + 64 字符 url-safe 随机串。前缀缺省取配置 API_KEY_PREFIX
        （default_config 保证恒有值，中性默认 ak-v1/，单一事实源）。"""
        if prefix is None:
            prefix = current_app.config["API_KEY_PREFIX"]
        return prefix + secrets.token_urlsafe(48)

    def create(self, user: Account, *, remark: str = "", is_active: bool = True) -> ApiKey:
        with db.auto_commit():
            record = ApiKey(
                user_id=user.id,
                api_key=self.generate_api_key(),
                is_active=is_active,
                remark=remark or "",
            )
            db.session.add(record)
        db.session.refresh(record)
        return record

    def get_by_credential(self, api_key: str) -> Optional[ApiKey]:
        """开放 API 鉴权用：按密钥串等值查（中间件调用，不做归属校验）。"""
        if not api_key:
            return None
        return db.session.query(ApiKey).filter(ApiKey.api_key == api_key).one_or_none()

    def get(self, user: Account, key_id: int) -> ApiKey:
        record = db.session.get(ApiKey, key_id)
        if not record:
            raise NotFoundException("API 密钥不存在")
        if record.user_id != user.id:
            raise ForbiddenException("无权访问该 API 密钥")
        return record

    def list_by_user(self, user: Account) -> list[ApiKey]:
        stmt = select(ApiKey).where(ApiKey.user_id == user.id).order_by(desc(ApiKey.created_at))
        return list(db.session.scalars(stmt))

    def update(self, user: Account, key_id: int, **kwargs) -> ApiKey:
        record = self.get(user, key_id)
        allowed = {"remark", "is_active"}
        with db.auto_commit():
            for k, v in kwargs.items():
                if k in allowed and v is not None:
                    setattr(record, k, v)
        db.session.refresh(record)
        return record

    def delete(self, user: Account, key_id: int) -> None:
        record = self.get(user, key_id)
        with db.auto_commit():
            db.session.delete(record)
