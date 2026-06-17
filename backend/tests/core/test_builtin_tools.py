"""内置工具框架：YAML 三件套加载 + 懒 dynamic_import 链端到端（不需安装 ddgs/wikipedia）。

闸门要点：get_providers() 会对每个 provider 触发 dynamic_import 加载工具模块——工具模块顶层只依赖
langchain_core+pydantic+helper（langchain_community 在工厂体内懒导入，image_generation 的 service/storage 也在
_run 内懒导入），故此加载链在不装可选工具依赖时也通；跳过的 gaode 必须不在目录里（残留会让首次加载即 ModuleNotFoundError）。
"""
import re

from langchain_core.tools import BaseTool

from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.core.tools.builtin_tools.categories import BuiltinCategoryManager


def test_provider_manager_loads_all_kept_providers():
    mgr = BuiltinProviderManager()
    names = {p.name for p in mgr.get_providers()}
    assert names == {"google", "time", "duckduckgo", "wikipedia", "image_generation"}
    # 跳过项必须不存在
    assert mgr.get_provider("gaode") is None


def test_image_generation_provider_is_open_to_all():
    # v1.1：图像生成对所有登录用户开放（无管理员概念），provider admin_only=False，
    # 工具模块顶层只依赖 langchain_core+pydantic+helper（service/storage 在 _run 内懒导入），加载链不拉重依赖。
    mgr = BuiltinProviderManager()
    provider = mgr.get_provider("image_generation")
    assert provider is not None
    assert provider.provider_entity.admin_only is False
    factory = provider.get_tool("text_to_image")
    assert "prompt" in factory.args_schema.model_fields  # 免实例化即可读 args_schema
    assert isinstance(factory(), BaseTool)


def test_time_tool_instantiates_and_runs():
    mgr = BuiltinProviderManager()
    factory = mgr.get_provider("time").get_tool("current_time")
    tool = factory()
    assert isinstance(tool, BaseTool)
    # current_time 无参、无外部依赖，可直接跑
    out = tool.invoke({})
    assert isinstance(out, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", out)


def test_lazy_tool_factory_exposes_args_schema_without_instantiation():
    # duckduckgo/wikipedia/google 工厂用 add_attribute 把 args_schema 挂在函数上，
    # 无需实例化（也就无需装 ddgs/wikipedia/community）即可读出入参 schema。
    mgr = BuiltinProviderManager()
    factory = mgr.get_provider("duckduckgo").get_tool("duckduckgo_search")
    assert "query" in factory.args_schema.model_fields


def test_tool_entities_metadata_loaded():
    mgr = BuiltinProviderManager()
    provider = mgr.get_provider("time")
    entity = provider.get_tool_entity("current_time")
    assert entity.name == "current_time" and entity.label == "获取当前时间"


def test_category_manager_loads_icons():
    cmap = BuiltinCategoryManager().get_category_map()
    assert set(cmap.keys()) == {"search", "weather", "tool"}
    # icon 被读成 svg 文本
    assert cmap["search"]["icon"].lstrip().startswith("<")
