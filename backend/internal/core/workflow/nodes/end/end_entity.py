"""结束节点数据实体。"""
from pydantic import Field

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity


class EndNodeData(BaseNodeData):
    """结束节点数据：outputs 即整个工作流（工具）的出参定义。"""

    outputs: list[VariableEntity] = Field(default_factory=list)
