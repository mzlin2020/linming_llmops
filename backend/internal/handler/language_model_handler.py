"""LanguageModelHandler：对外暴露 provider/model 目录，只读。

只读所以端点都是 GET。所有端点都要求登录（语言模型清单是平台内部资源，不对游客暴露）。
"""
from dataclasses import dataclass

from flask import Response as FlaskResponse
from injector import inject

from internal.middleware import RequireLogin
from internal.service import LanguageModelService
from pkg.response import not_found_message, success


@inject
@dataclass
class LanguageModelHandler:
    language_model_service: LanguageModelService

    @RequireLogin
    def list_models(self):
        """GET /api/language-models —— 列出所有 provider，每个 provider 内嵌它的模型卡。"""
        providers = self.language_model_service.list_providers()
        return success([p.model_dump(mode="json") for p in providers])

    @RequireLogin
    def get_provider(self, provider: str):
        """GET /api/language-models/<provider> —— 单 provider 详情。"""
        entity = self.language_model_service.get_provider(provider)
        return success(entity.model_dump(mode="json"))

    @RequireLogin
    def get_model(self, provider: str, model: str):
        """GET /api/language-models/<provider>/<model> —— 单模型详情。"""
        entity = self.language_model_service.get_model(provider, model)
        return success(entity.model_dump(mode="json"))

    @RequireLogin
    def get_provider_icon(self, provider: str):
        """GET /api/language-models/<provider>/icon —— 取 provider icon。

        icon 不存在直接返回 {code:404}，不走业务异常（免得 logger 报 ERROR）。
        """
        result = self.language_model_service.read_icon(provider)
        if result is None:
            return not_found_message(f"provider {provider} 无 icon")
        data, mime = result
        return FlaskResponse(data, mimetype=mime, status=200)
