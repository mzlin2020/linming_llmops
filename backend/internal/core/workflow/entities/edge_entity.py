"""工作流边实体（pydantic v2）。"""
from uuid import UUID

from pydantic import BaseModel

from .node_entity import NodeType


class BaseEdgeData(BaseModel):
    """基础边数据：连接两个节点，source/target 为节点 id。"""

    id: UUID
    source: UUID  # 边起点节点 id
    source_type: NodeType
    target: UUID  # 边终点节点 id
    target_type: NodeType
