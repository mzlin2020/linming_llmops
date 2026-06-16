"""内置工具服务：把 BuiltinProviderManager / BuiltinCategoryManager 暴露给 handler 层。

只读：列分类、列 provider+工具、取单个工具详情、取 provider 图标。
本轮不与 chat/app/agent 串联——仅工具子系统自身的目录浏览基建。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from injector import inject
from pydantic import BaseModel

from internal.core.tools.builtin_tools import providers as _providers_pkg
from internal.core.tools.builtin_tools.categories import BuiltinCategoryManager
from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.exception import NotFoundException

_PROVIDERS_DIR = Path(_providers_pkg.__file__).resolve().parent
_ICON_MIME = {
    "svg": "image/svg+xml",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


@inject
@dataclass
class BuiltinToolService:
    builtin_provider_manager: BuiltinProviderManager
    builtin_category_manager: BuiltinCategoryManager

    def get_builtin_tools(self) -> list[dict]:
        """列出所有 provider + 其下工具（含入参 schema）。icon 不内联，走单独的 icon 端点。"""
        builtin_tools = []
        for provider in self.builtin_provider_manager.get_providers():
            entity = provider.provider_entity
            item = {**entity.model_dump(exclude={"icon"}), "tools": []}
            for tool_entity in provider.get_tool_entities():
                tool = provider.get_tool(tool_entity.name)
                item["tools"].append({
                    **tool_entity.model_dump(),
                    "inputs": self.get_tool_inputs(tool),
                })
            builtin_tools.append(item)
        return builtin_tools

    def get_provider_tool(self, provider_name: str, tool_name: str) -> dict:
        """单个工具详情。"""
        provider = self.builtin_provider_manager.get_provider(provider_name)
        if provider is None:
            raise NotFoundException(message=f"提供商 {provider_name} 不存在")
        tool_entity = provider.get_tool_entity(tool_name)
        if tool_entity is None:
            raise NotFoundException(message=f"工具 {tool_name} 不存在")
        entity = provider.provider_entity
        tool = provider.get_tool(tool_name)
        return {
            "provider": {**entity.model_dump(exclude={"icon", "created_at"})},
            **tool_entity.model_dump(),
            "created_at": entity.created_at,
            "inputs": self.get_tool_inputs(tool),
        }

    def get_categories(self) -> list[dict]:
        """所有分类（category / name / icon-svg 文本）。"""
        category_map = self.builtin_category_manager.get_category_map()
        return [{
            "category": c["entity"].category,
            "name": c["entity"].name,
            "icon": c["icon"],
        } for c in category_map.values()]

    def get_provider_icon(self, provider_name: str) -> Optional[tuple[bytes, str]]:
        """返回 (bytes, mimetype)；provider/icon 不存在则 None（由 handler 转 404）。"""
        provider = self.builtin_provider_manager.get_provider(provider_name)
        if provider is None:
            return None
        icon = provider.provider_entity.icon
        if not icon:
            return None
        icon_path = _PROVIDERS_DIR / provider_name / "_asset" / icon
        if not icon_path.exists():
            return None
        ext = icon_path.suffix.lower().lstrip(".")
        mime = _ICON_MIME.get(ext, "application/octet-stream")
        return icon_path.read_bytes(), mime

    @classmethod
    def get_tool_inputs(cls, tool: Any) -> list[dict]:
        """从工具工厂函数挂的 args_schema 读出入参（pydantic v2）。无 schema 则空列表。"""
        inputs: list[dict] = []
        args_schema = getattr(tool, "args_schema", None)
        if not (isinstance(args_schema, type) and issubclass(args_schema, BaseModel)):
            return inputs
        for field_name, field in args_schema.model_fields.items():
            annotation = field.annotation
            inputs.append({
                "name": field_name,
                "description": field.description or "",
                "required": field.is_required(),
                "type": getattr(annotation, "__name__", str(annotation)),
            })
        return inputs
