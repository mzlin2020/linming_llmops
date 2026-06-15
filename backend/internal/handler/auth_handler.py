from dataclasses import dataclass

from flask import current_app, request
from injector import inject

from internal.exception import ForbiddenException, UnauthorizedException
from internal.schema.auth_schema import LoginReq, RefreshReq, RegisterReq
from internal.service import AccountService, JwtService
from pkg.response import success


@inject
@dataclass
class AuthHandler:
    account_service: AccountService
    jwt_service: JwtService

    def register(self):
        if not current_app.config.get("ALLOW_REGISTRATION"):
            raise ForbiddenException("注册已关闭")
        req = self._parse(RegisterReq)
        account = self.account_service.create_account(req.email, req.password, req.name)
        return success(self._tokens(account))

    def login(self):
        req = self._parse(LoginReq)
        account = self.account_service.verify_credentials(req.email, req.password)
        if not account:
            raise UnauthorizedException("邮箱或密码错误")
        if not account.is_active:
            raise UnauthorizedException("账户已禁用")
        return success(self._tokens(account))

    def refresh(self):
        req = self._parse(RefreshReq)
        payload = self.jwt_service.parse_token(req.refresh_token, expected_type="refresh")
        account = self.account_service.get_account(payload.get("sub"))
        if not account or not account.is_active:
            raise UnauthorizedException("账户不存在或已禁用")
        return success({"access_token": self.jwt_service.generate_access_token(account)})

    def logout(self):
        # 无状态 JWT：登出由客户端丢弃令牌完成
        return success({})

    def _tokens(self, account) -> dict:
        return {
            "access_token": self.jwt_service.generate_access_token(account),
            "refresh_token": self.jwt_service.generate_refresh_token(account),
            "account": account.to_dict(),
        }

    @staticmethod
    def _parse(model_cls):
        # 校验失败抛 pydantic ValidationError，由全局错误处理统一映射为 422
        return model_cls(**(request.get_json(silent=True) or {}))
