"""默认 provider/model 解析（叶子模块）。

chat 链路、工作流 llm 节点、LanguageModelManager.get_default 共用同一条回落链：
配置 dict → DEFAULT_LLM_PROVIDER / DEFAULT_LLM_MODEL 环境变量 → 内置默认值（OpenAI 兼容）。
"""
import os
from typing import Any, Optional


def resolve_default_provider_model(cfg: Optional[dict[str, Any]] = None) -> tuple[str, str]:
    """从模型配置 dict 取 provider/model，缺省回落环境变量默认值。"""
    cfg = cfg or {}
    provider = cfg.get("provider") or os.getenv("DEFAULT_LLM_PROVIDER") or "openai"
    model = cfg.get("model") or os.getenv("DEFAULT_LLM_MODEL") or "gpt-4o-mini"
    return provider, model
