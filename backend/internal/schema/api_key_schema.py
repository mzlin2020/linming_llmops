"""开放 API 密钥管理请求 schema（pydantic v2）。

响应不另建 schema：handler 直接组装 dict 用 success(...) 包裹（对齐 api_tool_handler 风格）。
"""
from typing import Optional

from pydantic import BaseModel, Field


class CreateApiKeyReq(BaseModel):
    remark: str = Field(default="", max_length=255, description="备注")
    is_active: bool = Field(default=True, description="是否启用")


class UpdateApiKeyReq(BaseModel):
    remark: Optional[str] = Field(default=None, max_length=255, description="备注")
    is_active: Optional[bool] = Field(default=None, description="是否启用")
