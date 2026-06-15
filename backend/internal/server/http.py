import logging
import os

from flask import Flask
from flask_cors import CORS
from flask_login import LoginManager
from flask_migrate import Migrate
from pydantic import ValidationError

from config import Config
from internal.exception import CustomException
from internal.extension import celery_extension, logging_extension, redis_extension
from internal.middleware import Middleware
from internal.router import Router
from pkg.response import HttpCode, Response, json
from pkg.sqlalchemy import SQLAlchemy

# 触发 ORM 模型 import，让 db.metadata 完整加载，Alembic 才能 autogenerate
from internal import model  # noqa: F401


class Http(Flask):
    """Http 服务引擎：装载 config → 全局错误处理 → 初始化扩展 → CORS → 注册 middleware/router"""

    def __init__(
        self,
        *args,
        conf: Config,
        db: SQLAlchemy,
        migrate: Migrate,
        login_manager: LoginManager,
        middleware: Middleware,
        router: Router,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.config.from_object(conf)
        self.register_error_handler(Exception, self._error_handler)

        db.init_app(self)
        migrate.init_app(self, db, directory="internal/migration")
        redis_extension.init_app(self)
        celery_extension.init_app(self)
        logging_extension.init_app(self)
        login_manager.init_app(self)

        CORS(self, resources={r"/*": {"origins": "*", "supports_credentials": True}})

        login_manager.request_loader(middleware.request_loader)

        router.register_router(self)

    def _error_handler(self, error: Exception):
        logging.error("An error occurred: %s", error, exc_info=True)
        if isinstance(error, CustomException):
            return json(Response(code=error.code, message=error.message or "fail", data=error.data or {}))
        # pydantic 请求体校验失败统一映射为 422，handler 直接构造 schema 即可、无需各自 try/except
        if isinstance(error, ValidationError):
            errors = error.errors()
            msg = errors[0].get("msg", "参数校验失败") if errors else "参数校验失败"
            return json(Response(code=HttpCode.VALIDATE_ERROR.value, message=msg, data={}))
        # werkzeug 内置 HTTPException(405/404/...) 保留原状态码，
        # 否则像 405 Method Not Allowed 会被错误地映射成 500。
        from werkzeug.exceptions import HTTPException
        if isinstance(error, HTTPException):
            return json(Response(code=error.code or HttpCode.INTERNAL_ERROR.value, message=error.name or "fail", data={}))
        if self.debug or os.getenv("FLASK_ENV") == "development":
            raise error
        return json(Response(code=HttpCode.INTERNAL_ERROR.value, message="fail", data=str(error)))
