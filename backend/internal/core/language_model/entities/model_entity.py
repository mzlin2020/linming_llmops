"""模型卡（model.yaml）的 schema。"""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ModelType(str, Enum):
    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    RERANK = "rerank"
    TEXT2IMG = "text2img"
    TTS = "tts"
    STT = "stt"


class ModelFeature(str, Enum):
    TOOL_CALL = "tool_call"
    FUNCTION_CALL = "function_call"
    VISION = "vision"
    STREAMING = "streaming"
    JSON_MODE = "json_mode"
    REASONING = "reasoning"
    AGENT_THOUGHT = "agent_thought"


class ParameterType(str, Enum):
    INT = "int"
    FLOAT = "float"
    STRING = "string"
    BOOLEAN = "boolean"


class ParameterRule(BaseModel):
    name: str
    label: dict[str, str] = Field(default_factory=dict, description="多语言标签 {zh_Hans, en_US}")
    type: ParameterType = ParameterType.FLOAT
    required: bool = False
    default: Optional[float | int | str | bool] = None
    min: Optional[float] = None
    max: Optional[float] = None
    options: list[str] = Field(default_factory=list, description="枚举型可选值")
    help: dict[str, str] = Field(default_factory=dict)


class Pricing(BaseModel):
    """计费信息，可选；为后续 token 计费铺垫。"""
    input: float = Field(0.0, description="输入价格，每 unit token")
    output: float = Field(0.0, description="输出价格，每 unit token")
    unit: str = Field("0.001", description="计价单位 token 数（千分位字符串）")
    currency: str = Field("USD", description="币种")


class ModelEntity(BaseModel):
    """单个模型卡，对应一份 model.yaml。"""

    model_config = {"protected_namespaces": ()}  # 允许字段以 model_ 开头

    model_name: str = Field(..., description="模型在 provider 内的唯一名，对应上游 SDK 的 model 参数")
    label: dict[str, str] = Field(default_factory=dict, description="多语言展示名")
    model_type: ModelType = ModelType.CHAT
    features: list[ModelFeature] = Field(default_factory=list)
    context_window: int = Field(4096, description="上下文窗口大小")
    max_output_tokens: Optional[int] = Field(None, description="单次最大输出 tokens")
    parameter_rules: list[ParameterRule] = Field(default_factory=list)
    pricing: Optional[Pricing] = None
    deprecated: bool = False
    # 「可见但仅受限可用」标记：模型目录仍会列出（前端可据此展示），但调用入口在后端按 is_admin 拦截。
    # 当前用于文生图（按张计费、成本敏感）等受限能力。
    admin_only: bool = False
