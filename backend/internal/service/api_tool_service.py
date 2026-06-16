"""ApiToolService：自定义 API 工具（插件）服务。

本期（Phase 4b）仅前置移植 get_owned_tool 一个归属查询方法——AppConfigService 校验应用绑定的
自定义工具是否归属当前用户时需要它。OpenAPI 解析 / CRUD / 插件商店等全量能力随 Phase 4c 的工具纵切补齐。
"""
from dataclasses import dataclass
from typing import Optional

from injector import inject

from internal.extension.database_extension import db
from internal.model import ApiTool


@inject
@dataclass
class ApiToolService:
    def get_owned_tool(self, provider_id: int, tool_name: str, user_id: int) -> Optional[ApiTool]:
        """按 provider_id + tool_name 取归属 user_id 的工具行；不存在/越权返回 None。"""
        return db.session.query(ApiTool).filter(
            ApiTool.provider_id == provider_id,
            ApiTool.name == tool_name,
            ApiTool.user_id == user_id,
        ).one_or_none()
