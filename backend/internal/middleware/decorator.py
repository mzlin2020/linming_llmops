"""接口装饰器。`@RequireLogin` 要求有效登录；`@RequirePermission` 在无 RBAC 下
移植为「仅校验登录」的放行版（保留签名，供 Phase 4 移植 handler 时沿用）。
"""
from functools import wraps
from typing import Callable

from flask_login import current_user

from internal.exception import UnauthorizedException

REQUIRE_LOGIN_KEY = "__require_login__"
REQUIRE_PERMISSION_KEY = "__require_permissions__"


def _ensure_authenticated() -> None:
    # Flask-Login 的 request_loader 已在 before-request 阶段把 account 塞进 current_user
    if not getattr(current_user, "is_authenticated", False):
        raise UnauthorizedException("该接口需要登录")


def RequireLogin(func: Callable) -> Callable:
    """要求接口必须携带有效 JWT。public 接口不加此装饰器。"""
    setattr(func, REQUIRE_LOGIN_KEY, True)

    @wraps(func)
    def wrapper(*args, **kwargs):
        _ensure_authenticated()
        return func(*args, **kwargs)

    setattr(wrapper, REQUIRE_LOGIN_KEY, True)
    return wrapper


def RequirePermission(*codes: str) -> Callable:
    """无 RBAC：等价于仅要求登录。保留 *codes 签名以便后续 handler 原样移植。"""

    def decorator(func: Callable) -> Callable:
        setattr(func, REQUIRE_LOGIN_KEY, True)
        setattr(func, REQUIRE_PERMISSION_KEY, list(codes))

        @wraps(func)
        def wrapper(*args, **kwargs):
            _ensure_authenticated()
            return func(*args, **kwargs)

        setattr(wrapper, REQUIRE_LOGIN_KEY, True)
        setattr(wrapper, REQUIRE_PERMISSION_KEY, list(codes))
        return wrapper

    return decorator
