"""文生图工具（Agent 画图）。

让带工具的 Agent 能在对话里调用已配置的生图模型出图，返回 markdown 图片链接供前端渲染。

访问控制：本平台无管理员概念，图像生成对所有登录用户开放（provider admin_only=false）；
成本由 ImageGenerationService 内的每日配额兜底。生图模型未配置（DEFAULT_IMAGE_PROVIDER/MODEL 为空）时，
service 抛友好错误，本工具转成文字反馈，不会让对话崩。

依赖（flask current_user / service）在 _run 内懒加载：本工具在 Agent 流式执行（stream_with_context）
中运行，请求/应用上下文仍存活，current_user / current_app.config / db.session 均可用。
"""
from types import SimpleNamespace
from typing import Any, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from internal.lib.helper import add_attribute


class TextToImageArgsSchema(BaseModel):
    prompt: str = Field(description="对要生成图片的详细文字描述，越具体越好")
    size: str = Field(default="2048x2048", description="图片尺寸，如 2048x2048 / 2560x1440 / 4K（部分模型要求≥约369万像素，更小会被上游以 400 拒绝）")


class TextToImageTool(BaseTool):
    name: str = "text_to_image"
    description: str = "当用户要求画图 / 生成图片 / 出图时使用：根据文字描述生成一张图片，返回图片链接。"
    args_schema: Type[BaseModel] = TextToImageArgsSchema

    def _run(self, *args: Any, **kwargs: Any) -> str:
        from flask_login import current_user

        from internal.core.language_model import LanguageModelManager
        from internal.exception import CustomException
        from internal.service.image_generation_service import ImageGenerationService
        from internal.service.quota_service import QuotaService
        from internal.storage import StorageService

        prompt = (kwargs.get("prompt") or "").strip()
        if not prompt:
            return "请提供要生成图片的文字描述"
        size = kwargs.get("size") or None

        service = ImageGenerationService(LanguageModelManager(), QuotaService(), StorageService())
        req = SimpleNamespace(prompt=prompt, provider=None, model=None, size=size, guidance_scale=None)
        try:
            result = service.text_to_image(current_user, req)
        except CustomException as e:  # service 已组装好友好信息（配额/未配置/上游失败），原样透传
            return e.message
        except Exception as e:  # noqa: BLE001 — 其它意外异常也转文字反馈，绝不让对话崩
            return f"图像生成失败：{str(e)[:160]}"
        url = result.get("url", "")
        return f"已生成图片：\n\n![{prompt[:50]}]({url})"


@add_attribute("args_schema", TextToImageArgsSchema)
def text_to_image(**kwargs: Any) -> BaseTool:
    """返回文生图工具。"""
    return TextToImageTool()
