"""内置工具子系统。

采用 providers/<name>/{positions.yaml, <tool>.yaml, <tool>.py} 三件套约定：
- BuiltinProviderManager：扫描 providers.yaml → 加载每个 provider 的工具
- BuiltinCategoryManager：扫描 categories.yaml + icons/
本轮仅做基建 + 浏览接口，尚未与 chat/app/agent 串联。
"""
from .categories import BuiltinCategoryManager
from .providers import BuiltinProviderManager

__all__ = ["BuiltinCategoryManager", "BuiltinProviderManager"]
