"""ImageGenerationHandler：文生图 / 图生图 / 生图历史 / 能力 URL 取图。

生成与历史端点要求登录（用 current_user 归属）；取图端点 serve_image_file 不要求登录——
它按不可猜的 uuid 能力 URL 提供图片，供 <img> / Agent markdown 直接加载（等价于公网图 URL）。
请求体用 pydantic v2 解析，响应用 pkg.response.success 包裹。
"""
from dataclasses import dataclass

from flask import Response as FlaskResponse
from flask import request
from flask_login import current_user
from injector import inject
from pydantic import ValidationError

from internal.exception import ValidateErrorException
from internal.lib.helper import first_validation_error as _first_error
from internal.middleware import RequireLogin
from internal.schema.image_schema import (
    GetImagesWithPageReq,
    ImageToImageReq,
    TextToImageReq,
)
from internal.service import ImageGenerationService
from pkg.response import not_found_message, success


@inject
@dataclass
class ImageGenerationHandler:
    image_generation_service: ImageGenerationService

    @RequireLogin
    def text_to_image(self):
        """POST /api/images/text-to-image —— 文生图。"""
        try:
            req = TextToImageReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        return success(self.image_generation_service.text_to_image(current_user, req))

    @RequireLogin
    def image_to_image(self):
        """POST /api/images/image-to-image —— 图生图。"""
        try:
            req = ImageToImageReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        return success(self.image_generation_service.image_to_image(current_user, req))

    @RequireLogin
    def list_images(self):
        """GET /api/images —— 生图历史/画廊分页。"""
        try:
            req = GetImagesWithPageReq.model_validate(request.args.to_dict(flat=True))
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        return success(self.image_generation_service.list_images(
            current_user, req.current_page, req.page_size,
        ))

    def serve_image_file(self, name: str):
        """GET /api/images/file/<name> —— 按能力 URL（不可猜 uuid）读取生成图，无需登录。"""
        result = self.image_generation_service.read_image_file(name)
        if result is None:
            return not_found_message("图片不存在")
        data, mime = result
        # 文件名是内容寻址的不可猜 uuid，字节永不变 —— 画廊/对话里同一图会被反复 <img> 加载，
        # 上长缓存避免每次渲染都回源读盘。
        return FlaskResponse(
            data,
            mimetype=mime,
            status=200,
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )
