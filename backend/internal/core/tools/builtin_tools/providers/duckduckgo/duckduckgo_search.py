"""DuckDuckGo 搜索工具。

无需任何 API key。langchain_community 在工厂体内懒加载，模块导入期只依赖 pydantic + langchain_core，
避免缺包拖垮服务启动；args_schema 通过 add_attribute 挂在工厂函数上，因此无需实例化即可读出入参。
实际调用需容器内装有 `ddgs` 包（langchain-community 0.4.x 只认 `import ddgs`，旧名 duckduckgo-search 不再提供该模块）。
"""
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from internal.lib.helper import add_attribute


class DuckDuckGoSearchArgsSchema(BaseModel):
    query: str = Field(description="需要搜索的查询语句。")


@add_attribute("args_schema", DuckDuckGoSearchArgsSchema)
def duckduckgo_search(**kwargs: Any) -> BaseTool:
    """返回 DuckDuckGo 搜索工具。"""
    from langchain_community.tools import DuckDuckGoSearchRun

    return DuckDuckGoSearchRun(
        description=(
            "一个注重隐私的搜索引擎。当你需要搜索时事信息时可以使用该工具，"
            "该工具的输入是一个查询语句。"
        ),
        args_schema=DuckDuckGoSearchArgsSchema,
    )
