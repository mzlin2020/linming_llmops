"""自定义 API 工具请求 schema（pydantic v2，按本项目风格）。

响应不另建 schema：service 直接组装 dict（对齐 builtin_tool_service 风格），handler 用 success(...) 包裹。
"""
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from internal.schema.conversation_schema import PaginatorReq


def _validate_headers(v):
    if v is None:
        return []
    if not isinstance(v, list):
        raise ValueError("headers 必须是列表")
    for header in v:
        if not isinstance(header, dict) or set(header.keys()) != {"key", "value"}:
            raise ValueError("headers 的每个元素必须且仅包含 key/value 两个字段")
    return v


class ValidateOpenAPISchemaReq(BaseModel):
    openapi_schema: str = Field(..., min_length=1, description="OpenAPI schema JSON 字符串")


class _ApiToolProviderReq(BaseModel):
    """创建 / 更新工具提供者的共用请求体（字段与 headers 校验一致）。"""
    name: str = Field(..., min_length=1, max_length=64, description="工具提供者名")
    icon: str = Field(..., min_length=1, max_length=512, description="图标 URL")
    openapi_schema: str = Field(..., min_length=1, description="OpenAPI schema JSON 字符串")
    headers: list = Field(default_factory=list, description="公共请求头 [{key,value}]")

    @field_validator("headers")
    @classmethod
    def check_headers(cls, v):
        return _validate_headers(v)


class CreateApiToolReq(_ApiToolProviderReq):
    pass


class UpdateApiToolProviderReq(_ApiToolProviderReq):
    pass


class GetApiToolProvidersWithPageReq(PaginatorReq):
    search_word: Optional[str] = Field(default=None, description="按名称模糊搜索")


class PublishApiToolReq(BaseModel):
    """发布 / 取消发布到公共插件商店（发布与取消共用一个端点）。"""
    is_public: bool = Field(..., description="True=上架到商店，False=从商店下架")
