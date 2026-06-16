"""OpenAPI 规范的数据结构与校验（增强 operationId 字符校验）。

只取 get/post 方法；参数字段 name/in/description/required/type，in∈{path,query,header,cookie,
request_body}，type∈{str,int,float,bool}。增强项：operationId 必须为标识符安全字符
（^[a-zA-Z0-9_-]+$），因为生成的 LangChain 工具名为 f"{id}_{operationId}"，含空格/点会破坏 tool_call。
"""
import re
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from internal.exception import ValidateErrorException

# operationId 字符约束：多数模型/供应商要求工具名匹配 ^[a-zA-Z0-9_-]+$
_OPERATION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


class ParameterType(str, Enum):
    """参数支持的类型。"""
    STR = "str"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"


ParameterTypeMap = {
    ParameterType.STR: str,
    ParameterType.INT: int,
    ParameterType.FLOAT: float,
    ParameterType.BOOL: bool,
}


class ParameterIn(str, Enum):
    """参数支持存放的位置。"""
    PATH = "path"
    QUERY = "query"
    HEADER = "header"
    COOKIE = "cookie"
    REQUEST_BODY = "request_body"


class OpenAPISchema(BaseModel):
    """OpenAPI 规范的数据结构。"""
    server: str = Field(default="", validate_default=True, description="工具提供者的服务基础地址")
    description: str = Field(default="", validate_default=True, description="工具提供者的描述信息")
    paths: dict[str, dict] = Field(default_factory=dict, validate_default=True, description="工具提供者的路径参数字典")

    @field_validator("server", mode="before")
    def validate_server(cls, server: str) -> str:
        if server is None or server == "":
            raise ValidateErrorException("server 不能为空且为字符串")
        return server

    @field_validator("description", mode="before")
    def validate_description(cls, description: str) -> str:
        if description is None or description == "":
            raise ValidateErrorException("description 不能为空且为字符串")
        return description

    @field_validator("paths", mode="before")
    def validate_paths(cls, paths: dict[str, dict]) -> dict[str, dict]:
        """校验 paths：方法提取、operationId 唯一 + 字符约束、parameters 校验。"""
        if not paths or not isinstance(paths, dict):
            raise ValidateErrorException("openapi_schema 中的 paths 不能为空且必须为字典")

        methods = ["get", "post"]
        interfaces = []
        for path, path_item in paths.items():
            for method in methods:
                if method in path_item:
                    interfaces.append({"path": path, "method": method, "operation": path_item[method]})

        operation_ids = []
        extra_paths = {}
        for interface in interfaces:
            operation = interface["operation"]
            if not isinstance(operation.get("description"), str):
                raise ValidateErrorException("description 不能为空且为字符串")
            if not isinstance(operation.get("operationId"), str):
                raise ValidateErrorException("operationId 不能为空且为字符串")
            if not _OPERATION_ID_RE.match(operation["operationId"]):
                raise ValidateErrorException(
                    f"operationId 只能包含字母/数字/下划线/中划线：{operation['operationId']}"
                )
            if not isinstance(operation.get("parameters", []), list):
                raise ValidateErrorException("parameters 必须是列表或者为空")

            if operation["operationId"] in operation_ids:
                raise ValidateErrorException(f"operationId 必须唯一，{operation['operationId']} 出现重复")
            operation_ids.append(operation["operationId"])

            for parameter in operation.get("parameters", []):
                if not isinstance(parameter.get("name"), str):
                    raise ValidateErrorException("parameter.name 参数必须为字符串且不为空")
                if not isinstance(parameter.get("description"), str):
                    raise ValidateErrorException("parameter.description 参数必须为字符串且不为空")
                if not isinstance(parameter.get("required"), bool):
                    raise ValidateErrorException("parameter.required 参数必须为布尔值且不为空")
                if (
                    not isinstance(parameter.get("in"), str)
                    or parameter.get("in") not in ParameterIn.__members__.values()
                ):
                    raise ValidateErrorException(
                        f"parameter.in 参数必须为 {'/'.join([item.value for item in ParameterIn])}"
                    )
                if (
                    not isinstance(parameter.get("type"), str)
                    or parameter.get("type") not in ParameterType.__members__.values()
                ):
                    raise ValidateErrorException(
                        f"parameter.type 参数必须为 {'/'.join([item.value for item in ParameterType])}"
                    )

            extra_paths[interface["path"]] = {
                interface["method"]: {
                    "description": operation["description"],
                    "operationId": operation["operationId"],
                    "parameters": [{
                        "name": parameter.get("name"),
                        "in": parameter.get("in"),
                        "description": parameter.get("description"),
                        "required": parameter.get("required"),
                        "type": parameter.get("type"),
                    } for parameter in operation.get("parameters", [])],
                }
            }

        return extra_paths
