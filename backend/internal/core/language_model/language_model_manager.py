"""LanguageModelManager：从 DB（ai_llm_provider/model/channel）把 (provider, model) 翻译成 langchain Chat 实例。

数据源是 DB（管理后台可增删改）；icon 等静态资源放 providers/ 目录。

缓存与失效（不拖慢热路径）：
- 目录（provider/model/channel 配置 + 解密后的凭证）在内存字典缓存。
- 用 redis 整数 ai:llm:catalog_version 做失效信号；_ensure_loaded 加**进程内短 TTL 守护**
  （_CACHE_TTL 秒内不重复查 redis），绝大多数调用是纯内存命中。版本变化（=后台改过配置）才查一次 DB 重建。
- API Key 在重建目录时一次性解密并缓存，**非每请求解密**。

多渠道（仅 multi_channel provider，如第三方中转）：一个模型挂多个渠道，按 priority 兜底；
熔断走 redis（见 channel_router）。普通 provider 完全不进 failover 代码路径，零额外开销。

凭证安全：ProviderEntity（公开元数据，供 /api/language-models 序列化）永不含密钥；
密钥只在运行期的 ProviderCredential 里，由 build_provider 注入 provider 对象。
"""
from __future__ import annotations

import time
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Optional

from internal.exception import FailException, NotFoundException
from internal.lib import crypto

from .channel_router import ChannelRouter, FailoverChatModel
from .entities import ModelEntity, ProviderCredential, ProviderEntity
from .providers.base import BaseLanguageModelProvider, build_provider

_PROVIDERS_DIR = Path(__file__).parent / "providers"
_CATALOG_VERSION_KEY = "ai:llm:catalog_version"


class _Channel:
    __slots__ = ("id", "credential", "models")

    def __init__(self, id: int, credential: ProviderCredential, models: list[str]):
        self.id = id
        self.credential = credential
        self.models = models


class _CatalogProvider:
    __slots__ = ("entity", "multi_channel", "credential", "channels")

    def __init__(self, entity, multi_channel, credential, channels):
        self.entity: ProviderEntity = entity
        self.multi_channel: bool = multi_channel
        self.credential: ProviderCredential = credential
        self.channels: list[_Channel] = channels


class LanguageModelManager:
    """provider 注册中心 + 模型实例化入口（DB 驱动）。

    没有构造依赖（DI 用 ClassProvider 自动构造）；redis/db 都走全局扩展单例，配置走 current_app.config。
    """

    _CACHE_TTL = 8.0  # 进程内「版本检查」节流秒数：此窗口内不再查 redis，直接用内存目录

    def __init__(self):
        self._cache: dict[str, _CatalogProvider] = {}
        self._loaded: bool = False
        self._version: Optional[int] = None
        self._last_check: float = 0.0
        self._lock: Lock = Lock()
        self._router: Optional[ChannelRouter] = None

    # ----------------------------------------------------- 加载 / 失效

    @staticmethod
    def _read_version() -> int:
        from internal.extension.redis_extension import redis_client

        try:
            v = redis_client.get(_CATALOG_VERSION_KEY)
            return int(v) if v else 0
        except Exception:
            return 0

    def _ensure_loaded(self) -> None:
        now = time.monotonic()
        if self._loaded and (now - self._last_check) < self._CACHE_TTL:
            return
        with self._lock:
            now = time.monotonic()
            if self._loaded and (now - self._last_check) < self._CACHE_TTL:
                return
            ver = self._read_version()
            if self._loaded and ver == self._version:
                self._last_check = now
                return
            self._reload()
            self._version = ver
            self._loaded = True
            self._last_check = now

    def _reload(self) -> None:
        from internal.extension.database_extension import db
        from internal.model import LlmChannel, LlmModel, LlmProvider

        cache: dict[str, _CatalogProvider] = {}
        providers = (
            db.session.query(LlmProvider)
            .filter(LlmProvider.enabled.is_(True))
            .order_by(LlmProvider.sort, LlmProvider.id)
            .all()
        )
        for p in providers:
            model_rows = (
                db.session.query(LlmModel)
                .filter(LlmModel.provider_id == p.id, LlmModel.enabled.is_(True))
                .order_by(LlmModel.sort, LlmModel.id)
                .all()
            )
            models = [
                ModelEntity.model_validate({
                    "model_name": m.model_name,
                    "label": m.label or {},
                    "model_type": m.model_type or "chat",
                    "features": m.features or [],
                    "context_window": m.context_window or 4096,
                    "max_output_tokens": m.max_output_tokens,
                    "parameter_rules": m.parameter_rules or [],
                    "pricing": m.pricing,
                    "deprecated": bool(m.deprecated),
                    "admin_only": bool(m.admin_only),
                })
                for m in model_rows
            ]
            entity = ProviderEntity.model_validate({
                "name": p.name,
                "label": p.label or {},
                "description": p.description or {},
                "icon": p.icon or None,
                "background": p.background or None,
                "supported_model_types": p.supported_model_types or ["chat"],
                "api_key_env": p.api_key_env or None,
                "base_url_env": None,
                "default_base_url": None,
                "protocol": p.protocol or "openai",
                "models": models,
            })
            single_cred = ProviderCredential(
                api_key=crypto.decrypt(p.api_key_cipher) or None,
                base_url=p.base_url or None,
            )
            channels: list[_Channel] = []
            if p.multi_channel:
                channel_rows = (
                    db.session.query(LlmChannel)
                    .filter(LlmChannel.provider_id == p.id, LlmChannel.enabled.is_(True))
                    .order_by(LlmChannel.priority, LlmChannel.id)
                    .all()
                )
                for c in channel_rows:
                    channels.append(_Channel(
                        id=c.id,
                        credential=ProviderCredential(
                            api_key=crypto.decrypt(c.api_key_cipher) or None,
                            base_url=c.base_url or None,
                        ),
                        models=list(c.models or []),
                    ))
            cache[p.name] = _CatalogProvider(
                entity=entity, multi_channel=bool(p.multi_channel),
                credential=single_cred, channels=channels,
            )
        self._cache = cache

    @staticmethod
    def bump_version() -> None:
        """管理写操作后调用：INCR 目录版本号，令所有进程/容器在下次检查时重载。"""
        from internal.extension.redis_extension import redis_client

        try:
            redis_client.incr(_CATALOG_VERSION_KEY)
        except Exception:
            pass

    def _get_router(self) -> ChannelRouter:
        if self._router is None:
            from flask import current_app

            try:
                th = int(current_app.config.get("CHANNEL_FAILURE_THRESHOLD", 3))
                cd = int(current_app.config.get("CHANNEL_COOLDOWN_SECONDS", 300))
            except Exception:
                th, cd = 3, 300
            self._router = ChannelRouter(th, cd)
        return self._router

    @staticmethod
    def _default_pm() -> tuple[str, str]:
        from .defaults import resolve_default_provider_model

        return resolve_default_provider_model()

    # ----------------------------------------------------- 只读查询

    def list_providers(self) -> list[ProviderEntity]:
        self._ensure_loaded()
        return [cp.entity for cp in self._cache.values()]

    def get_provider(self, name: str) -> ProviderEntity:
        self._ensure_loaded()
        cp = self._cache.get(name)
        if cp is None:
            raise NotFoundException(message=f"provider 不存在: {name}")
        return cp.entity

    def get_model_entity(self, provider: str, model: str) -> ModelEntity:
        entity = self.get_provider(provider).find_model(model)
        if entity is None:
            raise NotFoundException(message=f"provider {provider} 下不存在模型 {model}")
        return entity

    def calculate_price(
        self, provider: Optional[str], model: Optional[str],
        input_tokens: int, output_tokens: int,
    ) -> dict:
        """本地查表算价：total_price = (in*input + out*output) * float(unit)。
        无 provider/model、无 pricing、或任何异常 → 全 0。"""
        zero = {"input_unit_price": 0.0, "output_unit_price": 0.0, "price_unit": 0.0, "total_price": 0.0}
        if not provider or not model:
            return zero
        try:
            pricing = self.get_model_entity(provider, model).pricing
        except Exception:
            return zero
        if pricing is None:
            return zero
        try:
            unit = float(pricing.unit)
        except (TypeError, ValueError):
            unit = 0.0
        in_tok = int(input_tokens or 0)
        out_tok = int(output_tokens or 0)
        total = (in_tok * pricing.input + out_tok * pricing.output) * unit
        return {
            "input_unit_price": float(pricing.input),
            "output_unit_price": float(pricing.output),
            "price_unit": unit,
            "total_price": round(total, 7),
        }

    def _has_feature(self, provider: str, model: str, feature) -> bool:
        """(provider, model) 是否声明某能力；不存在安全回 False。"""
        try:
            return feature in self.get_model_entity(provider, model).features
        except Exception:
            return False

    def supports_tool_call(self, provider: str, model: str) -> bool:
        """是否声明原生 tool_call（决定能否走 FunctionCallAgent）；不存在回 False（降级无工具对话）。"""
        from .entities.model_entity import ModelFeature

        return self._has_feature(provider, model, ModelFeature.TOOL_CALL)

    def supports_vision(self, provider: str, model: str) -> bool:
        """是否声明 vision（图片理解）；不存在回 False（聊天入口据此拒带图请求）。"""
        from .entities.model_entity import ModelFeature

        return self._has_feature(provider, model, ModelFeature.VISION)

    # ----------------------------------------------------- 实例化

    def _resolve_or_degrade(self, provider: str, model: str) -> tuple[_CatalogProvider, str]:
        """取目标 (provider, model) 的目录条目；若已被删/禁用，优雅降级到默认模型。"""
        cp = self._cache.get(provider)
        if cp is not None and cp.entity.find_model(model) is not None:
            return cp, model
        dprovider, dmodel = self._default_pm()
        dcp = self._cache.get(dprovider)
        if dcp is None:
            raise NotFoundException(message=f"provider 不存在: {provider}")
        if dcp.entity.find_model(dmodel) is None:
            if not dcp.entity.models:
                raise NotFoundException(message=f"默认 provider {dprovider} 无可用模型")
            dmodel = dcp.entity.models[0].model_name
        return dcp, dmodel

    def instantiate(self, provider: str, model: str, **kwargs: Any) -> Any:
        self._ensure_loaded()
        cp, model = self._resolve_or_degrade(provider, model)
        if cp.multi_channel:
            return self._build_failover_chat(cp, model, **kwargs)
        return build_provider(cp.entity, cp.credential).instantiate(model, **kwargs)

    def _build_failover_chat(self, cp: _CatalogProvider, model: str, **kwargs: Any) -> Any:
        params = {"max_retries": 0}  # 让坏渠道快速失败再切；单渠道路径保留默认重试
        params.update(kwargs)
        runnables: list[tuple] = []
        for ch in cp.channels:
            if ch.models and model not in ch.models:
                continue
            try:
                rb = build_provider(cp.entity, ch.credential).instantiate(model, **params)
            except Exception:
                continue  # 该渠道连实例化都失败（如缺 key）→ 跳过
            runnables.append((ch.id, rb))
        if not runnables:
            # 多渠道 provider 没配可用渠道 → 回落默认（避免直接 500）
            dprovider, dmodel = self._default_pm()
            dcp = self._cache.get(dprovider)
            if dcp is not None and not dcp.multi_channel and dcp.entity.find_model(dmodel) is not None:
                return build_provider(dcp.entity, dcp.credential).instantiate(dmodel, **kwargs)
            raise FailException(message=f"provider {cp.entity.name} 无可用渠道")
        return FailoverChatModel(runnables, self._get_router(), model)

    def get_default(self) -> Any:
        provider, model = self._default_pm()
        return self.instantiate(provider, model)

    def generate_images(
        self, provider: str, model: str, prompt: str, *, image: Any = None, **params: Any
    ) -> list[dict]:
        """文生图 / 图生图：返回上游 data 数组。multi_channel provider 走渠道兜底。"""
        return self._dispatch(provider, model, lambda prov: prov.generate_images(model, prompt, image=image, **params))

    def synthesize_speech(self, provider: str, model: str, text: str, **opts: Any) -> bytes:
        """文本转语音：返回完整音频字节。multi_channel provider 走渠道兜底（注：TTS 协议通常读 env，
        不消费渠道凭证，多渠道对其无差别——多渠道主要面向 openai/anthropic）。"""
        return self._dispatch(provider, model, lambda prov: prov.synthesize_speech(model, text, **opts))

    def _dispatch(self, provider: str, model: str, fn: Callable[[BaseLanguageModelProvider], Any]) -> Any:
        """非聊天链路（文生图 / TTS）的统一入口：单渠道直发；multi_channel 走渠道兜底。"""
        self._ensure_loaded()
        cp = self._cache.get(provider)
        if cp is None:
            raise NotFoundException(message=f"provider 不存在: {provider}")
        if cp.multi_channel:
            candidates = [(ch.id, ch) for ch in cp.channels if not ch.models or model in ch.models]
            return self._get_router().run(candidates, lambda ch: fn(build_provider(cp.entity, ch.credential)))
        return fn(build_provider(cp.entity, cp.credential))

    # ----------------------------------------------------- 资源（icon）

    def read_provider_icon(self, provider: str) -> Optional[tuple[bytes, str]]:
        """返回 (bytes, mimetype)。icon 为 URL（新建 provider）或不存在则返回 None。"""
        entity = self.get_provider(provider)
        icon = entity.icon
        if not icon or icon.startswith("http"):
            return None
        icon_path = _PROVIDERS_DIR / provider / icon
        if not icon_path.exists():
            return None
        ext = icon_path.suffix.lower().lstrip(".")
        mime = {
            "svg": "image/svg+xml",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
        }.get(ext, "application/octet-stream")
        return icon_path.read_bytes(), mime
