"""LlmSeedService：把 providers/ 下的 YAML 内置目录幂等灌入 DB（ai_llm_provider/model）。

定位是**开机种子**（CLI `seed-llm-catalog` / entrypoint 调用），与运行期管理面（LlmAdminService）分开：
- **不受 ENABLE_LLM_ADMIN 守护**——内置模型是否预置由独立的 SEED_LLM_CATALOG 开关决定；管理面编辑另由
  ENABLE_LLM_ADMIN 守护。两者职责不同。
- **按 provider.name 幂等**：已存在的 provider 整体跳过——绝不覆盖用户在管理面的改动（也不向其补插新模型）。
  新增内置 provider 随版本发布、由本服务补齐；既有 provider 的演进交给管理面或新一轮 YAML（改名）。
- **密钥不入仓**：api_key_cipher 留空，YAML 只声明 api_key_env，运行期凭证读取回落环境变量。

写入后 bump_version()，令运行期目录缓存（含其它进程/容器）下次重载。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union
from pathlib import Path

from injector import inject

from internal.core.language_model.language_model_manager import LanguageModelManager
from internal.core.language_model.seed_loader import load_seed_providers
from internal.extension.database_extension import db
from internal.model import LlmModel, LlmProvider


@inject
@dataclass
class LlmSeedService:
    manager: LanguageModelManager

    def seed_builtin_catalog(
        self, providers_dir: Optional[Union[str, Path]] = None
    ) -> dict:
        """幂等灌入内置目录。返回 {imported, skipped, models} 统计。"""
        seeds = load_seed_providers(providers_dir)
        existing = {name for (name,) in db.session.query(LlmProvider.name).all()}

        imported = skipped = models_imported = 0
        with db.auto_commit():
            for sp in seeds:
                if sp["name"] in existing:
                    skipped += 1
                    continue
                provider = LlmProvider(
                    name=sp["name"],
                    label=sp["label"],
                    description=sp["description"],
                    icon=sp["icon"],
                    background=sp["background"],
                    supported_model_types=sp["supported_model_types"],
                    protocol=sp["protocol"],
                    multi_channel=sp["multi_channel"],
                    base_url=sp["base_url"],
                    api_key_cipher="",
                    api_key_env=sp["api_key_env"],
                    enabled=sp["enabled"],
                    sort=sp["sort"],
                )
                db.session.add(provider)
                db.session.flush()  # 取回 provider.id 供模型外键
                for m in sp["models"]:
                    db.session.add(LlmModel(
                        provider_id=provider.id,
                        model_name=m["model_name"],
                        label=m["label"],
                        model_type=m["model_type"],
                        features=m["features"],
                        context_window=m["context_window"],
                        max_output_tokens=m["max_output_tokens"],
                        parameter_rules=m["parameter_rules"],
                        pricing=m["pricing"],
                        deprecated=m["deprecated"],
                        admin_only=m["admin_only"],
                        is_default=m["is_default"],
                        enabled=m["enabled"],
                        sort=m["sort"],
                    ))
                    models_imported += 1
                imported += 1

        if imported:
            self.manager.bump_version()
        return {"imported": imported, "skipped": skipped, "models": models_imported}
