from dataclasses import dataclass, field
from typing import Any, Generator, Union

from flask import jsonify, stream_with_context, Response as FlaskResponse

from .http_code import HttpCode


@dataclass
class Response:
    """统一响应体：{code: int(HTTP), message: str, data: any}"""
    code: int = HttpCode.SUCCESS.value
    message: str = "success"
    data: Any = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"code": int(self.code), "message": self.message, "data": self.data}


def json(resp: Response):
    """统一返回 (jsonify, http_status)；http_status 与 code 保持一致便于 nginx / 监控识别"""
    if resp is None:
        resp = Response()
    payload = resp.to_dict()
    status = payload["code"] if 100 <= payload["code"] < 600 else 200
    return jsonify(payload), status


def success(data: Any = None):
    return json(Response(code=HttpCode.SUCCESS.value, message="success", data=data if data is not None else {}))


def fail(msg: str = "fail", code: int = HttpCode.FAIL.value, data: Any = None):
    return json(Response(code=code, message="fail", data=msg if data is None else data))


def message(code: int = HttpCode.SUCCESS.value, msg: str = ""):
    return json(Response(code=code, message=msg, data={}))


def success_message(msg: str = ""):
    return message(code=HttpCode.SUCCESS.value, msg=msg)


def fail_message(msg: str = ""):
    return message(code=HttpCode.FAIL.value, msg=msg)


def validate_error_json(errors: Union[dict, list] = None):
    if isinstance(errors, dict) and errors:
        first_key = next(iter(errors))
        first_val = errors[first_key]
        msg = first_val[0] if isinstance(first_val, (list, tuple)) and first_val else str(first_val)
    elif isinstance(errors, list) and errors:
        msg = str(errors[0])
    else:
        msg = "参数校验失败"
    return json(Response(code=HttpCode.VALIDATE_ERROR.value, message=msg, data=errors or {}))


def unauthorized_message(msg: str = "未授权"):
    return message(code=HttpCode.UNAUTHORIZED.value, msg=msg)


def forbidden_message(msg: str = "无权限"):
    return message(code=HttpCode.FORBIDDEN.value, msg=msg)


def not_found_message(msg: str = "未找到"):
    return message(code=HttpCode.NOT_FOUND.value, msg=msg)


def compact_generate_response(response: Union[Response, Generator]) -> FlaskResponse:
    """统一处理块输出（Response）与流式 SSE 输出（Generator）"""
    if isinstance(response, Response):
        return json(response)

    def generate() -> Generator:
        yield from response

    return FlaskResponse(
        stream_with_context(generate()),
        status=200,
        mimetype="text/event-stream",
    )
