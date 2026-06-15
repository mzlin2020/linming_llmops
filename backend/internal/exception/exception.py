from dataclasses import dataclass, field
from typing import Any

from pkg.response import HttpCode


@dataclass
class CustomException(Exception):
    """自定义异常基类，最终被 Http._error_handler 转成统一响应壳"""
    message: str = ""
    code: int = HttpCode.FAIL.value
    data: Any = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


@dataclass
class FailException(CustomException):
    code: int = HttpCode.FAIL.value


@dataclass
class ValidateErrorException(CustomException):
    code: int = HttpCode.VALIDATE_ERROR.value


@dataclass
class NotFoundException(CustomException):
    code: int = HttpCode.NOT_FOUND.value


@dataclass
class UnauthorizedException(CustomException):
    code: int = HttpCode.UNAUTHORIZED.value


@dataclass
class ForbiddenException(CustomException):
    code: int = HttpCode.FORBIDDEN.value


@dataclass
class RateLimitException(CustomException):
    code: int = HttpCode.TOO_MANY_REQUESTS.value
