from enum import IntEnum


class HttpCode(IntEnum):
    """用 HTTP 状态码作为业务 code，便于 nginx / 监控直接识别"""
    SUCCESS = 200
    FAIL = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    VALIDATE_ERROR = 422
    TOO_MANY_REQUESTS = 429
    INTERNAL_ERROR = 500
