"""AI 模型目录管理请求 schema（pydantic v2）。

provider / model / channel 三类的增改。更新一律「字段给了才改」语义：
- 字符串/数值/布尔字段：给 None 表示不改（service 端 exclude_unset 取已设字段）。
- api_key：仅当传入非空字符串才覆盖加密落库；空/缺省 = 保留原密钥（避免改别的字段时把 key 抹掉）。

响应不另建 schema：service 直接组装 dict（含 key 掩码、渠道健康），handler 用 success(...) 包裹。
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

_MODEL_TYPES = {"chat", "completion", "embedding", "rerank", "text2img", "tts", "stt"}


# ---------------- provider ----------------

class CreateProviderReq(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    name: str = Field(..., min_length=1, max_length=64, description="唯一标识，全小写下划线")
    label: dict = Field(default_factory=dict, description="多语言展示名 {zh_Hans,en_US}")
    description: dict = Field(default_factory=dict, description="多语言描述")
    icon: str = Field(default="", max_length=512, description="icon URL 或旧目录文件名")
    background: str = Field(default="", max_length=32)
    supported_model_types: list[str] = Field(default_factory=lambda: ["chat"])
    protocol: str = Field(default="openai", max_length=32, description="协议 key（须匹配协议注册表，如 openai/anthropic）")
    multi_channel: bool = Field(default=False, description="true=走渠道池兜底（如第三方中转）")
    base_url: str = Field(default="", max_length=512, description="单渠道模式 base_url")
    api_key: str = Field(default="", description="单渠道模式明文 API Key（加密落库；更新时空=保留）")
    api_key_env: str = Field(default="", max_length=128, description="旧 env 变量名兜底")
    enabled: bool = Field(default=True)
    sort: int = Field(default=0)


class UpdateProviderReq(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    label: Optional[dict] = None
    description: Optional[dict] = None
    icon: Optional[str] = Field(default=None, max_length=512)
    background: Optional[str] = Field(default=None, max_length=32)
    supported_model_types: Optional[list[str]] = None
    protocol: Optional[str] = Field(default=None, max_length=32)
    multi_channel: Optional[bool] = None
    base_url: Optional[str] = Field(default=None, max_length=512)
    api_key: Optional[str] = Field(default=None, description="非空才覆盖；空/缺省=保留原密钥")
    api_key_env: Optional[str] = Field(default=None, max_length=128)
    enabled: Optional[bool] = None
    sort: Optional[int] = None


# ---------------- model ----------------

class _ModelBody(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    label: dict = Field(default_factory=dict)
    model_type: str = Field(default="chat", description="chat/text2img/tts/embedding...")
    features: list[str] = Field(default_factory=list, description='["tool_call","vision","streaming"...]')
    context_window: int = Field(default=4096, ge=1)
    max_output_tokens: Optional[int] = Field(default=None, ge=1)
    parameter_rules: list = Field(default_factory=list)
    pricing: Optional[dict] = None
    deprecated: bool = False
    admin_only: bool = False
    is_default: bool = False
    enabled: bool = True
    sort: int = 0

    @field_validator("model_type")
    @classmethod
    def _check_type(cls, v):
        if v not in _MODEL_TYPES:
            raise ValueError(f"模型类型须是 {', '.join(sorted(_MODEL_TYPES))} 之一")
        return v


class CreateModelReq(_ModelBody):
    model_name: str = Field(..., min_length=1, max_length=128, description="上游 SDK 的 model 参数")


class UpdateModelReq(BaseModel):
    """更新：全部可选，给了才改。"""
    model_config = ConfigDict(protected_namespaces=())

    model_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    label: Optional[dict] = None
    model_type: Optional[str] = None
    features: Optional[list[str]] = None
    context_window: Optional[int] = Field(default=None, ge=1)
    max_output_tokens: Optional[int] = Field(default=None, ge=1)
    parameter_rules: Optional[list] = None
    pricing: Optional[dict] = None
    deprecated: Optional[bool] = None
    admin_only: Optional[bool] = None
    is_default: Optional[bool] = None
    enabled: Optional[bool] = None
    sort: Optional[int] = None

    @field_validator("model_type")
    @classmethod
    def _check_type(cls, v):
        if v is not None and v not in _MODEL_TYPES:
            raise ValueError(f"模型类型须是 {', '.join(sorted(_MODEL_TYPES))} 之一")
        return v


# ---------------- channel（仅 multi_channel provider）----------------

class CreateChannelReq(BaseModel):
    name: str = Field(default="", max_length=128, description="渠道备注名")
    base_url: str = Field(..., min_length=1, max_length=512, description="该渠道 base_url")
    api_key: str = Field(default="", description="该渠道明文 API Key（加密落库）")
    priority: int = Field(default=0, description="越小越先试")
    models: list[str] = Field(default_factory=list, description="model_name 白名单，空=全部")
    enabled: bool = Field(default=True)


class UpdateChannelReq(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    base_url: Optional[str] = Field(default=None, max_length=512)
    api_key: Optional[str] = Field(default=None, description="非空才覆盖；空/缺省=保留原密钥")
    priority: Optional[int] = None
    models: Optional[list[str]] = None
    enabled: Optional[bool] = None
