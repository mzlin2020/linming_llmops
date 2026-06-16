"""大语言模型节点数据实体。"""
from typing import Any

from pydantic import Field, field_validator

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity, VariableValueType


class LLMNodeData(BaseNodeData):
    """大语言模型节点数据。

    language_model_config 形如 {"provider": ..., "model": ..., "parameters": {...}}；
    外部 JSON 键名是 model_config（对齐应用编排），但 pydantic v2 里 model_config 是保留名，
    字段名只能叫 language_model_config + alias。
    """

    prompt: str = ""  # jinja2 模板提示词
    language_model_config: dict[str, Any] = Field(alias="model_config", default_factory=dict)
    inputs: list[VariableEntity] = Field(default_factory=list)
    outputs: list[VariableEntity] = Field(
        default_factory=lambda: [
            VariableEntity(name="output", value={"type": VariableValueType.GENERATED})
        ]
    )

    @field_validator("outputs", mode="before")
    @classmethod
    def validate_outputs(cls, outputs):
        return [VariableEntity(name="output", value={"type": VariableValueType.GENERATED})]
