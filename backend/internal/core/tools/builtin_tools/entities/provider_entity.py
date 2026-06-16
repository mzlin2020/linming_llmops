"""服务提供商实体 + 自加载的 Provider。

ProviderEntity 映射 providers.yaml 的每条记录；Provider 在构造后（model_post_init）按该 provider
目录下的 positions.yaml 读取工具顺序，加载每个工具的 <tool>.yaml 元数据，并动态导入工具工厂函数。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

from internal.lib.helper import dynamic_import

from .tool_entity import ToolEntity

# entities/ 的上级是 builtin_tools/，其下 providers/ 即各 provider 目录
_PROVIDERS_DIR = Path(__file__).resolve().parent.parent / "providers"
_PROVIDERS_PKG = "internal.core.tools.builtin_tools.providers"


class ProviderEntity(BaseModel):
    """服务提供商实体，映射 providers.yaml。"""

    name: str
    label: str
    description: str = ""
    icon: str = ""
    background: str = ""
    category: str = ""
    created_at: int = 0
    # 「可见但仅超管可用」：目录仍列出（前端据此置灰+提示），但 ToolResolver 在非超管时会跳过该 provider 的工具，
    # 且编排页绑定校验会拒绝非超管把它加进自己的 app。当前用于图像生成（按张计费、成本敏感）。
    admin_only: bool = False


class Provider(BaseModel):
    """一个服务提供商：聚合它下面的全部工具元数据与工具工厂函数。"""

    name: str
    position: int
    provider_entity: ProviderEntity
    tool_entity_map: dict[str, ToolEntity] = Field(default_factory=dict)
    tool_func_map: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        self._provider_init()

    def get_tool(self, tool_name: str) -> Any:
        return self.tool_func_map.get(tool_name)

    def get_tool_entity(self, tool_name: str) -> Optional[ToolEntity]:
        return self.tool_entity_map.get(tool_name)

    def get_tool_entities(self) -> list[ToolEntity]:
        return list(self.tool_entity_map.values())

    def _provider_init(self) -> None:
        provider_path = _PROVIDERS_DIR / self.name
        positions = yaml.safe_load((provider_path / "positions.yaml").read_text(encoding="utf-8")) or []
        for tool_name in positions:
            tool_data = yaml.safe_load(
                (provider_path / f"{tool_name}.yaml").read_text(encoding="utf-8")
            ) or {}
            self.tool_entity_map[tool_name] = ToolEntity(**tool_data)
            self.tool_func_map[tool_name] = dynamic_import(f"{_PROVIDERS_PKG}.{self.name}", tool_name)
