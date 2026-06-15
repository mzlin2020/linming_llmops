from dataclasses import dataclass
from typing import Optional

from flask import Request
from injector import inject

from internal.exception import UnauthorizedException
from internal.model import Account
from internal.service import AccountService, JwtService


@inject
@dataclass
class Middleware:
    """Flask-Login request_loader：解 Bearer access JWT → 查 account → 设 current_user。
    无 Authorization 头视为匿名（public 接口可访问；需登录的接口由 @RequireLogin 拦截）。
    开放 API 的 API-Key 鉴权路径留到 Phase 4（需 ai_api_key 表）。"""
    jwt_service: JwtService
    account_service: AccountService

    @staticmethod
    def _bearer_credential(auth_header: str) -> str:
        if " " not in auth_header:
            raise UnauthorizedException("Authorization 头格式错误")
        auth_schema, credential = auth_header.split(None, 1)
        if auth_schema.lower() != "bearer":
            raise UnauthorizedException("仅支持 Bearer 授权")
        return credential

    def request_loader(self, request: Request) -> Optional[Account]:
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None
        credential = self._bearer_credential(auth_header)

        payload = self.jwt_service.parse_token(credential, expected_type="access")
        account_id = payload.get("sub")
        if account_id is None:
            raise UnauthorizedException("token 缺少 sub")

        account = self.account_service.get_account(account_id)
        if not account:
            raise UnauthorizedException("用户不存在，请重新登录")
        if not account.is_active:
            raise UnauthorizedException("账户已禁用")

        # 接缝兼容：无 RBAC，permissions/roles 恒为空，供 @RequirePermission 兜底读取
        request.jwt_payload = payload
        request.jwt_permissions = []
        request.jwt_roles = []
        return account
