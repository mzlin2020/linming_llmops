"""内置工具分类管理器。

读取本目录 categories.yaml + icons/，把每个分类装成 {entity, icon(svg文本)}。
风格对齐 internal/core/language_model/language_model_manager.py：纯类、懒加载、线程安全；
无外部依赖，injector 自动构造。
"""
from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any

import yaml

from internal.core.tools.builtin_tools.entities import CategoryEntity
from internal.exception import NotFoundException

_DIR = Path(__file__).resolve().parent
_CATEGORIES_YAML = _DIR / "categories.yaml"
_ICONS_DIR = _DIR / "icons"


class BuiltinCategoryManager:
    def __init__(self) -> None:
        self._category_map: dict[str, Any] = {}
        self._loaded: bool = False
        self._lock: Lock = Lock()

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            categories = yaml.safe_load(_CATEGORIES_YAML.read_text(encoding="utf-8")) or []
            for category in categories:
                entity = CategoryEntity(**category)
                icon_path = _ICONS_DIR / entity.icon
                if not icon_path.exists():
                    raise NotFoundException(message=f"分类 {entity.category} 的 icon 未提供: {entity.icon}")
                self._category_map[entity.category] = {
                    "entity": entity,
                    "icon": icon_path.read_text(encoding="utf-8"),
                }
            self._loaded = True

    def get_category_map(self) -> dict[str, Any]:
        self._ensure_loaded()
        return self._category_map
