"""API 工具提供者管理器：据 ToolEntity 动态生成 LangChain StructuredTool。

设计要点：
- 普通类（injector 自动构造，与 BuiltinProviderManager 一致），不引 BaseModel/多重装饰；
- 出站请求统一走 _safe_http.safe_request（SSRF 防护 + 超时），不裸用 requests.request。
"""
from __future__ import annotations

from typing import Callable, Optional, Type

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field, create_model

from internal.core.tools.api_tools.entities import ParameterIn, ParameterTypeMap, ToolEntity
from internal.core.tools.api_tools.providers._safe_http import UnsafeRequestError, safe_request


class ApiProviderManager:
    """据传递的工具配置信息生成自定义 LangChain 工具。"""

    @classmethod
    def _create_tool_func_from_tool_entity(cls, tool_entity: ToolEntity) -> Callable:
        """根据传递的信息创建发起 API 请求的函数。"""

        def tool_func(**kwargs) -> str:
            # 1. 按位置分桶 path/query/header/cookie/request_body
            parameters = {
                ParameterIn.PATH: {},
                ParameterIn.HEADER: {},
                ParameterIn.QUERY: {},
                ParameterIn.COOKIE: {},
                ParameterIn.REQUEST_BODY: {},
            }
            parameter_map = {parameter.get("name"): parameter for parameter in tool_entity.parameters}
            header_map = {header.get("key"): header.get("value") for header in tool_entity.headers}

            # 2. 把 LLM 传入的实参分配到对应位置（默认 query）
            for key, value in kwargs.items():
                parameter = parameter_map.get(key)
                if parameter is None:
                    continue
                parameters[parameter.get("in", ParameterIn.QUERY)][key] = value

            # 3. SSRF 校验 + 带超时发起请求；不安全则把错误回给模型而非抛栈
            try:
                return safe_request(
                    method=tool_entity.method,
                    url=tool_entity.url.format(**parameters[ParameterIn.PATH]),
                    params=parameters[ParameterIn.QUERY],
                    json=parameters[ParameterIn.REQUEST_BODY],
                    headers={**header_map, **parameters[ParameterIn.HEADER]},
                    cookies=parameters[ParameterIn.COOKIE],
                ).text
            except UnsafeRequestError as e:
                return f"调用失败：{e}"

        return tool_func

    @classmethod
    def _create_model_from_parameters(cls, parameters: list[dict]) -> Type[BaseModel]:
        """根据 parameters 动态创建 args_schema（pydantic create_model）。"""
        fields = {}
        for parameter in parameters:
            field_name = parameter.get("name")
            field_type = ParameterTypeMap.get(parameter.get("type"), str)
            field_required = parameter.get("required", True)
            field_description = parameter.get("description", "")
            fields[field_name] = (
                field_type if field_required else Optional[field_type],
                Field(description=field_description),
            )
        return create_model("DynamicModel", **fields)

    def get_tool(self, tool_entity: ToolEntity) -> BaseTool:
        """据配置生成自定义 API 工具。工具名 f"{id}_{operationId}"，在 bind_tools 与 tool_call 间自洽。"""
        return StructuredTool.from_function(
            func=self._create_tool_func_from_tool_entity(tool_entity),
            name=f"{tool_entity.id}_{tool_entity.name}",
            description=tool_entity.description,
            args_schema=self._create_model_from_parameters(tool_entity.parameters),
        )
