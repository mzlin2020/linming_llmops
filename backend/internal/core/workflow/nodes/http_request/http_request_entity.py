"""HTTP 请求节点数据实体。"""
from enum import Enum
from typing import Optional

from pydantic import Field, HttpUrl, field_validator

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity, VariableType, VariableValueType
from internal.exception import ValidateErrorException


class HttpRequestMethod(str, Enum):
    """HTTP 请求方法枚举。"""

    GET = "get"
    POST = "post"
    PUT = "put"
    PATCH = "patch"
    DELETE = "delete"
    HEAD = "head"
    OPTIONS = "options"


class HttpRequestInputType(str, Enum):
    """HTTP 请求输入变量的归类。"""

    PARAMS = "params"  # query 参数
    HEADERS = "headers"  # 请求头
    BODY = "body"  # body 参数


class HttpRequestNodeData(BaseNodeData):
    """HTTP 请求节点数据。"""

    url: Optional[HttpUrl] = None  # pydantic v2 的 HttpUrl 是 Url 对象，使用处需 str()
    method: HttpRequestMethod = HttpRequestMethod.GET
    inputs: list[VariableEntity] = Field(default_factory=list)
    outputs: list[VariableEntity] = Field(
        default_factory=lambda: [
            VariableEntity(
                name="status_code",
                type=VariableType.INT,
                value={"type": VariableValueType.GENERATED, "content": 0},
            ),
            VariableEntity(name="text", value={"type": VariableValueType.GENERATED}),
        ],
    )

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, url):
        return url if url != "" else None

    @field_validator("outputs", mode="before")
    @classmethod
    def validate_outputs(cls, outputs):
        return [
            VariableEntity(
                name="status_code",
                type=VariableType.INT,
                value={"type": VariableValueType.GENERATED, "content": 0},
            ),
            VariableEntity(name="text", value={"type": VariableValueType.GENERATED}),
        ]

    @field_validator("inputs")
    @classmethod
    def validate_inputs(cls, inputs: list[VariableEntity]) -> list[VariableEntity]:
        """每个输入变量必须归类到 params/headers/body 之一。"""
        for input in inputs:
            if input.meta.get("type") not in (
                HttpRequestInputType.PARAMS,
                HttpRequestInputType.HEADERS,
                HttpRequestInputType.BODY,
            ):
                raise ValidateErrorException(message="Http请求参数结构出错")
        return inputs
