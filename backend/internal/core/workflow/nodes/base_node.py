"""工作流节点基类。

设计要点：统一给所有节点挂运行上下文（user_id / is_admin / flask_app），
图构建端零 if/elif 地用同一组 kwargs 实例化任意节点；触 DB/注入器的节点在 invoke 里
用 ensure_app_context() 兜底——LangGraph 并行分支跑在线程池 worker 线程，没有 Flask 上下文。
"""
from abc import ABC
from contextlib import contextmanager
from typing import Any, Optional

from langchain_core.runnables import RunnableSerializable
from pydantic import ConfigDict, Field

from internal.core.workflow.entities.node_entity import BaseNodeData


class BaseNode(RunnableSerializable, ABC):
    """工作流节点基类。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    node_data: BaseNodeData
    user_id: Optional[int] = None  # 运行该工作流的归属用户（归属过滤用）
    is_admin: bool = False  # 归属用户是否超管（admin_only 工具 / code 节点闸门）
    flask_app: Optional[Any] = Field(default=None, exclude=True)  # Flask 应用引用，worker 线程补上下文用

    @contextmanager
    def ensure_app_context(self):
        """无应用上下文（LangGraph worker 线程）时用 flask_app 补一个。"""
        from flask import has_app_context

        if self.flask_app is not None and not has_app_context():
            with self.flask_app.app_context():
                yield
        else:
            yield
