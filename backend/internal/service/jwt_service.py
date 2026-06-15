import time
from dataclasses import dataclass

import jwt
from flask import current_app
from injector import inject

from internal.exception import UnauthorizedException
from internal.model import Account


@inject
@dataclass
class JwtService:
    """自签 HS256 JWT。access/refresh 双令牌，payload 含 sub/type/email/iat/exp。"""

    def _secret(self) -> str:
        secret = current_app.config.get("JWT_SECRET")
        if not secret:
            raise UnauthorizedException("服务未配置 JWT_SECRET")
        return secret

    def _algorithm(self) -> str:
        return current_app.config.get("JWT_ALGORITHM") or "HS256"

    def _encode(self, account: Account, token_type: str, ttl: int) -> str:
        now = int(time.time())
        payload = {
            "sub": str(account.id),
            "type": token_type,
            "email": account.email,
            "iat": now,
            "exp": now + int(ttl),
        }
        return jwt.encode(payload, self._secret(), algorithm=self._algorithm())

    def generate_access_token(self, account: Account) -> str:
        return self._encode(account, "access", current_app.config.get("JWT_ACCESS_TOKEN_EXPIRES"))

    def generate_refresh_token(self, account: Account) -> str:
        return self._encode(account, "refresh", current_app.config.get("JWT_REFRESH_TOKEN_EXPIRES"))

    def parse_token(self, token: str, expected_type: str = None) -> dict:
        try:
            payload = jwt.decode(token, self._secret(), algorithms=[self._algorithm()])
        except jwt.ExpiredSignatureError:
            raise UnauthorizedException("token 失效，请重新登录")
        except jwt.InvalidTokenError:
            raise UnauthorizedException("token 无效")
        if expected_type and payload.get("type") != expected_type:
            raise UnauthorizedException("token 类型不匹配")
        return payload
