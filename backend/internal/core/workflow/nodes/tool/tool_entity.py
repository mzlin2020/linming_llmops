"""扩展插件（内置/自定义 API 工具）节点数据实体。"""
from typing import Any, Literal

from pydantic import Field, field_validator

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity, VariableValueType


class ToolNodeData(BaseNodeData):
    """工具节点数据。

    builtin_tool：provider_id=提供者名（如 time）、tool_id=工具名（如 current_time）；
    api_tool：provider_id=ai_api_tool_provider 的 int id（字符串形式）、tool_id=工具名（operationId）。
    """

    tool_type: Literal["builtin_tool", "api_tool", ""] = Field(alias="type")
    provider_id: str
    tool_id: str
    params: dict[str, Any] = Field(default_factory=dict)  # 内置工具的设置参数
    inputs: list[VariableEntity] = Field(default_factory=list)
    outputs: list[VariableEntity] = Field(
        default_factory=lambda: [
            VariableEntity(name="text", value={"type": VariableValueType.GENERATED})
        ]
    )

    @field_validator("outputs", mode="before")
    @classmethod
    def validate_outputs(cls, outputs):
        return [VariableEntity(name="text", value={"type": VariableValueType.GENERATED})]
