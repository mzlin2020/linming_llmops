from dataclasses import dataclass
from typing import Optional

from flask import Request
from injector import inject

from internal.exception import UnauthorizedException
from internal.model import Account
from internal.service import AccountService, ApiKeyService, JwtService


@inject
@dataclass
class Middleware:
    """Flask-Login request_loader：按蓝图分流——
    - openapi 蓝图：用 Authorization: Bearer <api_key> 走 API-Key 鉴权，current_user = 钥匙主人。
    - 其余蓝图：解 Bearer access JWT → 查 account → 设 current_user。
    无 Authorization 头视为匿名（public 接口可访问；需登录的接口由 @RequireLogin 拦截）。"""
    jwt_service: JwtService
    account_service: AccountService
    api_key_service: ApiKeyService

    @staticmethod
    def _bearer_credential(auth_header: str) -> str:
        if " " not in auth_header:
            raise UnauthorizedException("Authorization 头格式错误")
        auth_schema, credential = auth_header.split(None, 1)
        if auth_schema.lower() != "bearer":
            raise UnauthorizedException("仅支持 Bearer 授权")
        return credential

    def request_loader(self, request: Request) -> Optional[Account]:
        # 开放 API：单独走 API-Key 鉴权（无效/缺失直接抛 401，不放匿名进来）
        if request.blueprint == "openapi":
            return self._load_by_api_key(request)

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

    def _load_by_api_key(self, request: Request) -> Account:
        """开放 API 鉴权：Authorization: Bearer <api_key> → 查 ai_api_key → 返回钥匙归属账号。
        缺失 / 无效 / 已停用一律抛 401（不返回 None），确保匿名进不来。"""
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise UnauthorizedException("缺少 API 密钥")
        credential = self._bearer_credential(auth_header)

        record = self.api_key_service.get_by_credential(credential)
        if not record or not record.is_active:
            raise UnauthorizedException("API 密钥无效或已停用")

        account = self.account_service.get_account(record.user_id)
        if not account:
            raise UnauthorizedException("密钥归属用户不存在")
        if not account.is_active:
            raise UnauthorizedException("账户已禁用")
        return account
