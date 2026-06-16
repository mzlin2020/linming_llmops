"""LanguageModelService：把 LanguageModelManager 暴露给 handler 层。

为什么不直接让 handler 注入 manager？
- service 层是落「业务侧加工」的地方：比如未来要做「按用户权限过滤可见模型」、
  「把 model_entity 翻译成前端友好结构」、「加上缓存命中统计」，都在 service 里干。
- 现在 service 只是薄薄一层透传，但留了改造空间。
"""
from dataclasses import dataclass

from injector import inject

from internal.core.language_model.entities import ModelEntity, ProviderEntity
from internal.core.language_model.language_model_manager import LanguageModelManager


@inject
@dataclass
class LanguageModelService:
    manager: LanguageModelManager

    def list_providers(self) -> list[ProviderEntity]:
        return self.manager.list_providers()

    def get_provider(self, name: str) -> ProviderEntity:
        return self.manager.get_provider(name)

    def get_model(self, provider: str, model: str) -> ModelEntity:
        return self.manager.get_model_entity(provider, model)

    def read_icon(self, provider: str):
        return self.manager.read_provider_icon(provider)
