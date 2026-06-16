"""把 app 配置里的 tools JSON 解析成可执行的 LangChain BaseTool。

配置项形状：
    {"type": "builtin_tool", "provider": {"name": "time"}, "tool": {"name": "current_time", "params": {}}}
    {"type": "api_tool", "provider": {"id": 12, "name": "weather"}, "tool": {"id": 34, "name": "getWeather"}}

api_tool 从 ai_api_tool 取行 → ToolEntity → ApiProviderManager 造 StructuredTool（DB 用模块级
db.session 读，不反向 import service，避免 core→service 循环依赖）。

容错：provider/工具不存在、构造失败、非 BaseTool 一律跳过并 warning，绝不让对话整体失败。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from injector import inject
from langchain_core.tools import BaseTool
from sqlalchemy import tuple_
from sqlalchemy.orm import joinedload

from internal.core.tools.api_tools.entities import ToolEntity
from internal.core.tools.api_tools.providers import ApiProviderManager
from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.extension.database_extension import db
from internal.model import ApiTool


def find_owned_api_tools(
    pairs: list[tuple[int, str]], user_id: int, *, with_provider: bool = False
) -> list[ApiTool]:
    """按 (provider_id, 工具名) 对批量取归属 user_id 的自定义 API 工具行（一条 IN 查询）。

    with_provider=True 时 joinedload provider（要读 row.provider 的场景，避免逐行懒加载）。"""
    pairs = [p for p in pairs if p]
    if not pairs:
        return []
    query = db.session.query(ApiTool).filter(
        tuple_(ApiTool.provider_id, ApiTool.name).in_(pairs),
        ApiTool.user_id == user_id,
    )
    if with_provider:
        query = query.options(joinedload(ApiTool.provider))
    return query.all()


def find_owned_api_tool(
    provider_id: int, tool_name: str, user_id: int, *, with_provider: bool = False
) -> Optional[ApiTool]:
    """单条版：取归属 user_id 的一条自定义 API 工具行，不存在返回 None。"""
    rows = find_owned_api_tools([(provider_id, tool_name)], user_id, with_provider=with_provider)
    return rows[0] if rows else None


def build_api_tool_entity(row: ApiTool) -> ToolEntity:
    """ai_api_tool 行 → ToolEntity（7 字段构造的唯一出处；row.provider 需已加载）。"""
    return ToolEntity(
        id=str(row.id),
        name=row.name,
        url=row.url,
        method=row.method,
        description=row.description,
        headers=row.provider.headers or [],
        parameters=row.parameters or [],
    )


def instantiate_builtin_tool(
    manager: BuiltinProviderManager, provider_name: str, tool_name: str, params: Optional[dict] = None
) -> Optional[Any]:
    """从内置工具注册表取工厂并实例化；工厂不存在返回 None，构造异常向上抛（调用方各自兜底）。
    admin_only 闸由调用方处理（Agent 路跳过 vs 工作流节点抛 Forbidden，语义不同）。"""
    factory = manager.get_tool(provider_name, tool_name)
    if factory is None:
        return None
    return factory(**(params or {})) if callable(factory) else factory


@inject
@dataclass
class ToolResolver:
    builtin_provider_manager: BuiltinProviderManager
    api_provider_manager: ApiProviderManager

    def resolve(self, tools_config: Optional[list[dict]], *, is_admin: bool = False) -> list[BaseTool]:
        """is_admin：当前对话用户是否超管。非超管时跳过 admin_only 的内置工具（如图像生成），
        防止普通用户经「与已发布应用对话」等路径触发管理员专属能力。"""
        result: list[BaseTool] = []
        for item in tools_config or []:
            tool = self._resolve_one(item, is_admin)
            if tool is not None:
                result.append(tool)
        return result

    def _resolve_one(self, item: Any, is_admin: bool = False) -> Optional[BaseTool]:
        if not isinstance(item, dict):
            return None
        tool_type = item.get("type")
        if tool_type == "builtin_tool":
            return self._resolve_builtin(item, is_admin)
        if tool_type == "api_tool":
            return self._resolve_api(item)
        return None

    def _resolve_builtin(self, item: dict, is_admin: bool = False) -> Optional[BaseTool]:
        provider_name = (item.get("provider") or {}).get("name")
        tool_name = (item.get("tool") or {}).get("name")
        if not provider_name or not tool_name:
            return None
        # 管理员专属工具：非超管直接跳过（运行时硬闸；与编排页绑定校验、service 内 is_admin 三重防护）
        provider = self.builtin_provider_manager.get_provider(provider_name)
        if provider is not None and getattr(provider.provider_entity, "admin_only", False) and not is_admin:
            logging.info("非超管，跳过管理员专属工具：%s/%s", provider_name, tool_name)
            return None
        params = (item.get("tool") or {}).get("params") or {}
        try:
            tool = instantiate_builtin_tool(self.builtin_provider_manager, provider_name, tool_name, params)
        except Exception as e:
            logging.warning("agent 工具构造失败，已跳过：%s/%s（%s）", provider_name, tool_name, e)
            return None
        if tool is None:
            logging.warning("agent 工具未找到，已跳过：%s/%s", provider_name, tool_name)
            return None
        return tool if isinstance(tool, BaseTool) else None

    def _resolve_api(self, item: dict) -> Optional[BaseTool]:
        provider = item.get("provider") or {}
        tool = item.get("tool") or {}
        provider_id = provider.get("id")
        tool_id = tool.get("id")
        tool_name = tool.get("name")
        if not provider_id or not (tool_id or tool_name):
            return None
        try:
            # joinedload provider：tool_entity 要读 row.provider.headers，避免每个工具一次懒加载查询（聊天热路径）
            query = db.session.query(ApiTool).options(joinedload(ApiTool.provider)).filter(
                ApiTool.provider_id == provider_id
            )
            query = query.filter(ApiTool.id == tool_id) if tool_id else query.filter(ApiTool.name == tool_name)
            row = query.one_or_none()
            if row is None:
                logging.warning("agent 自定义工具未找到，已跳过：provider=%s tool=%s", provider_id, tool_id or tool_name)
                return None
            built = self.api_provider_manager.get_tool(build_api_tool_entity(row))
        except Exception as e:
            logging.warning("agent 自定义工具构造失败，已跳过：provider=%s tool=%s（%s）", provider_id, tool_id or tool_name, e)
            return None
        return built if isinstance(built, BaseTool) else None
