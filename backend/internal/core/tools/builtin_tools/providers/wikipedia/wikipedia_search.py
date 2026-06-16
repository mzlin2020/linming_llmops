"""维基百科搜索工具。

langchain_community + wikipedia 封装在工厂体内懒加载，模块导入期只依赖 pydantic + langchain_core，
避免缺包拖垮服务启动；args_schema 通过 add_attribute 挂在工厂函数上，因此无需实例化即可读出入参。
实际调用需容器内装有 `wikipedia` 包。
"""
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from internal.lib.helper import add_attribute


class WikipediaSearchArgsSchema(BaseModel):
    query: str = Field(description="需要查询的关键词或主题。")


@add_attribute("args_schema", WikipediaSearchArgsSchema)
def wikipedia_search(**kwargs: Any) -> BaseTool:
    """返回维基百科搜索工具。"""
    from langchain_community.tools import WikipediaQueryRun
    from langchain_community.utilities import WikipediaAPIWrapper

    return WikipediaQueryRun(
        description=(
            "一个用于执行维基百科搜索并提取词条摘要的工具。当你需要查询百科知识、"
            "人物、概念时可以使用，输入是一个关键词或主题。"
        ),
        args_schema=WikipediaSearchArgsSchema,
        api_wrapper=WikipediaAPIWrapper(top_k_results=3, lang="zh"),
    )
