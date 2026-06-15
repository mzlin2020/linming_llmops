from dataclasses import dataclass

from flask import Blueprint, Flask
from injector import inject

from internal.handler import AccountHandler, AuthHandler, PingHandler


@inject
@dataclass
class Router:
    ping_handler: PingHandler
    auth_handler: AuthHandler
    account_handler: AccountHandler

    def register_router(self, app: Flask):
        bp = Blueprint("api", __name__, url_prefix="/api")

        # 健康检查（public）
        bp.add_url_rule("/ping", view_func=self.ping_handler.ping, methods=["GET"])

        # 认证（public）
        bp.add_url_rule("/auth/register", view_func=self.auth_handler.register, methods=["POST"])
        bp.add_url_rule("/auth/login", view_func=self.auth_handler.login, methods=["POST"])
        bp.add_url_rule("/auth/refresh", view_func=self.auth_handler.refresh, methods=["POST"])
        bp.add_url_rule("/auth/logout", view_func=self.auth_handler.logout, methods=["POST"])

        # 账号（需登录）
        bp.add_url_rule("/account/me", view_func=self.account_handler.me, methods=["GET"])

        app.register_blueprint(bp)
