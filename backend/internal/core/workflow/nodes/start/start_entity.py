"""开始节点数据实体。"""
from pydantic import Field

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity


class StartNodeData(BaseNodeData):
    """开始节点数据：inputs 即整个工作流（工具）的入参定义。"""

    inputs: list[VariableEntity] = Field(default_factory=list)
