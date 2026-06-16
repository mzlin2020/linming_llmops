"""获取当前时间的工具（无参数、无外部依赖）。"""
from datetime import datetime
from typing import Any

from langchain_core.tools import BaseTool


class CurrentTimeTool(BaseTool):
    name: str = "current_time"
    description: str = "一个用于获取当前时间的工具。"

    def _run(self, *args: Any, **kwargs: Any) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def current_time(**kwargs: Any) -> BaseTool:
    """返回获取当前时间的 LangChain 工具。"""
    return CurrentTimeTool()
