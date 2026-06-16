"""模板转换节点数据实体。"""
from pydantic import Field, field_validator

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity, VariableValueType


class TemplateTransformNodeData(BaseNodeData):
    """模板转换节点数据：把多个输入变量按 jinja2 模板拼接成一个字符串。"""

    template: str = ""
    inputs: list[VariableEntity] = Field(default_factory=list)
    outputs: list[VariableEntity] = Field(
        default_factory=lambda: [
            VariableEntity(name="output", value={"type": VariableValueType.GENERATED})
        ]
    )

    @field_validator("outputs", mode="before")
    @classmethod
    def validate_outputs(cls, outputs):
        # 输出固定为单个 output 字段，前端传什么都重置
        return [VariableEntity(name="output", value={"type": VariableValueType.GENERATED})]
