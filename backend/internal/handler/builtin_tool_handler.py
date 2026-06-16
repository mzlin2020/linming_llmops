"""BuiltinToolHandler：内置工具目录浏览（只读）。

图标返回方式对齐 LanguageModelHandler（service 返回 (bytes, mime) | None，handler 转 FlaskResponse / 404）。
全部要求登录——平台内部资源，不对游客暴露。
"""
from dataclasses import dataclass

from flask import Response as FlaskResponse
from injector import inject

from internal.middleware import RequireLogin
from internal.service import BuiltinToolService
from pkg.response import not_found_message, success


@inject
@dataclass
class BuiltinToolHandler:
    builtin_tool_service: BuiltinToolService

    @RequireLogin
    def get_builtin_tools(self):
        """GET /api/builtin-tools —— 所有 provider + 工具。"""
        return success(self.builtin_tool_service.get_builtin_tools())

    @RequireLogin
    def get_categories(self):
        """GET /api/builtin-tools/categories —— 所有分类。"""
        return success(self.builtin_tool_service.get_categories())

    @RequireLogin
    def get_provider_tool(self, provider: str, tool: str):
        """GET /api/builtin-tools/<provider>/tools/<tool> —— 单工具详情。"""
        return success(self.builtin_tool_service.get_provider_tool(provider, tool))

    @RequireLogin
    def get_provider_icon(self, provider: str):
        """GET /api/builtin-tools/<provider>/icon —— provider 图标。"""
        result = self.builtin_tool_service.get_provider_icon(provider)
        if result is None:
            return not_found_message(f"提供商 {provider} 无 icon")
        data, mime = result
        return FlaskResponse(data, mimetype=mime, status=200)
