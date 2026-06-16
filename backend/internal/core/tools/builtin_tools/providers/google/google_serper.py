"""谷歌 Serper 搜索工具。

需要环境变量 SERPER_API_KEY。langchain_community 在工厂体内懒加载，模块导入期只依赖
pydantic + langchain_core，避免缺包拖垮服务启动；args_schema 通过 add_attribute 挂在工厂函数上，
因此无需实例化即可读出入参。
"""
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from internal.lib.helper import add_attribute


class GoogleSerperArgsSchema(BaseModel):
    query: str = Field(description="需要检索查询的语句。")


@add_attribute("args_schema", GoogleSerperArgsSchema)
def google_serper(**kwargs: Any) -> BaseTool:
    """返回谷歌 Serper 搜索工具。"""
    from langchain_community.tools import GoogleSerperRun
    from langchain_community.utilities import GoogleSerperAPIWrapper

    return GoogleSerperRun(
        name="google_serper",
        description=(
            "这是一个低成本的谷歌搜索 API。当你需要搜索时事信息时可以使用该工具，"
            "该工具的输入是一个查询语句。"
        ),
        args_schema=GoogleSerperArgsSchema,
        api_wrapper=GoogleSerperAPIWrapper(),
    )
