"""Provider 的 schema。"""
from typing import Optional

from pydantic import BaseModel, Field

from .model_entity import ModelEntity


class ProviderEntity(BaseModel):
    """一个 provider = 一组共享 base_url + api_key + 协议的上游入口。
    模型品牌差异化在 ModelEntity 层表达，不拆 provider。
    """

    name: str = Field(..., description="provider 唯一标识，目录名同名，全小写下划线")
    label: dict[str, str] = Field(default_factory=dict, description="多语言展示名")
    description: dict[str, str] = Field(default_factory=dict)
    icon: Optional[str] = Field(None, description="provider icon 文件名,相对 provider 目录")
    background: Optional[str] = Field(None, description="UI 主色背景，可选")
    supported_model_types: list[str] = Field(default_factory=lambda: ["chat"])
    api_key_env: Optional[str] = Field(
        None,
        description="该 provider 取 api_key 的环境变量名,如 OPENAI_API_KEY",
    )
    base_url_env: Optional[str] = Field(
        None, description="基础 URL 的环境变量名;若为空则用 default_base_url"
    )
    default_base_url: Optional[str] = Field(None, description="默认 base_url,可被环境变量覆盖")
    protocol: str = Field(
        "openai",
        description="上游接口协议,目前支持 openai / anthropic;影响实例化时调用的 ChatModel 类",
    )
    models: list[ModelEntity] = Field(default_factory=list)

    def find_model(self, model_name: str) -> Optional[ModelEntity]:
        for m in self.models:
            if m.model_name == model_name:
                return m
        return None
