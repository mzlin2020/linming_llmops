"""图像生成（文生图 / 图生图）请求 schema（pydantic v2）。

响应不另建 schema：service 直接组装 dict，handler 用 success(...) 包裹。
provider/model 为空时由 service 回落 DEFAULT_IMAGE_PROVIDER/MODEL，皆空则友好报错。
"""
from typing import Optional

from pydantic import BaseModel, Field

from internal.schema.conversation_schema import PaginatorReq


class TextToImageReq(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000, description="文本提示词")
    provider: Optional[str] = Field(default=None, max_length=64, description="生图 provider（缺省走默认）")
    model: Optional[str] = Field(default=None, max_length=128, description="生图模型（缺省走默认）")
    size: Optional[str] = Field(default=None, max_length=32, description="尺寸，如 1024x1024（缺省由上游取默认）")
    guidance_scale: Optional[float] = Field(default=None, ge=1, le=10, description="提示词相关性（仅部分模型支持）")


class ImageToImageReq(TextToImageReq):
    image_url: str = Field(..., min_length=1, max_length=1024, description="参考图公网 URL（须在白名单域名内）")


class GetImagesWithPageReq(PaginatorReq):
    pass
