"""内置工具服务提供商工厂。

扫描本目录 providers.yaml，为每个 provider 构造 Provider（Provider 自身会按 positions.yaml
加载 <tool>.yaml 元数据 + 动态导入工具工厂函数）。
风格对齐 internal/core/language_model/language_model_manager.py：纯类、懒加载、线程安全；
无外部依赖，injector 自动构造。
"""
from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any, Optional

import yaml

from internal.core.tools.builtin_tools.entities import Provider, ProviderEntity

_DIR = Path(__file__).resolve().parent
_PROVIDERS_YAML = _DIR / "providers.yaml"


class BuiltinProviderManager:
    def __init__(self) -> None:
        self._provider_map: dict[str, Provider] = {}
        self._loaded: bool = False
        self._lock: Lock = Lock()

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            data = yaml.safe_load(_PROVIDERS_YAML.read_text(encoding="utf-8")) or []
            for idx, provider_data in enumerate(data):
                entity = ProviderEntity(**provider_data)
                self._provider_map[entity.name] = Provider(
                    name=entity.name,
                    position=idx + 1,
                    provider_entity=entity,
                )
            self._loaded = True

    def get_provider(self, provider_name: str) -> Optional[Provider]:
        self._ensure_loaded()
        return self._provider_map.get(provider_name)

    def get_providers(self) -> list[Provider]:
        self._ensure_loaded()
        return list(self._provider_map.values())

    def get_provider_entities(self) -> list[ProviderEntity]:
        self._ensure_loaded()
        return [p.provider_entity for p in self._provider_map.values()]

    def get_tool(self, provider_name: str, tool_name: str) -> Any:
        provider = self.get_provider(provider_name)
        if provider is None:
            return None
        return provider.get_tool(tool_name)
