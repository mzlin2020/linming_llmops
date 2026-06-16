"""LlmAdminService：AI 模型目录（provider / model / channel）的管理 CRUD。

边界：
- 入口统一 _assert_llm_admin_enabled：模型目录是**全局共享**基建（无 user_id，所有对话共用，含加密凭证），
  故写入面由部署级开关 ENABLE_LLM_ADMIN（env，默认关）守护；关时一律 403（无管理员/角色概念，
  纯部署特性开关）。只读目录浏览走 language_model_service，不受此开关影响。
- API Key 以 Fernet 密文落库（internal/lib/crypto）；读出只回掩码，**永不**返回明文。
- 任何写操作后 LanguageModelManager.bump_version()，令运行期目录缓存（含其它进程/容器）下次重载。
- 渠道健康（熔断/失败计数）走 redis（channel_router），本服务只读它做展示、手动恢复删它。
"""
from __future__ import annotations

from dataclasses import dataclass

from flask import current_app
from injector import inject
from sqlalchemy.orm import selectinload

from internal.core.language_model.channel_router import ChannelRouter
from internal.core.language_model.language_model_manager import LanguageModelManager
from internal.core.language_model.providers.base import list_protocols
from internal.exception import ForbiddenException, NotFoundException, ValidateErrorException
from internal.extension.database_extension import db
from internal.lib import crypto
from internal.model import Account, LlmChannel, LlmModel, LlmProvider


@inject
@dataclass
class LlmAdminService:
    manager: LanguageModelManager

    # ---------------- 守卫 / 工具 ----------------

    @staticmethod
    def _assert_llm_admin_enabled() -> None:
        """模型目录写入面需部署侧显式开启 ENABLE_LLM_ADMIN（默认关）。
        无管理员/角色概念——这是部署级特性开关，非 per-user 权限。"""
        if not current_app.config.get("ENABLE_LLM_ADMIN"):
            raise ForbiddenException(message="AI 模型配置未开放（需在部署侧开启 ENABLE_LLM_ADMIN）")

    @staticmethod
    def _router() -> ChannelRouter:
        return ChannelRouter()  # health/recover 只读写 redis key，不依赖阈值

    @staticmethod
    def _get(cls, id_: int, label: str):
        row = db.session.get(cls, id_)
        if row is None:
            raise NotFoundException(message=f"{label}不存在")
        return row

    @staticmethod
    def _apply(row, data: dict, fields: tuple) -> None:
        """把 data 里「给了且非 None」的字段写回 row（更新通用 setattr 循环）。"""
        for f in fields:
            if f in data and data[f] is not None:
                setattr(row, f, data[f])

    # ---------------- 协议 ----------------

    def list_protocols(self, user: Account) -> list[str]:
        self._assert_llm_admin_enabled()
        return list_protocols()

    # ---------------- provider ----------------

    def list_providers(self, user: Account) -> list[dict]:
        self._assert_llm_admin_enabled()
        rows = (
            db.session.query(LlmProvider)
            .options(selectinload(LlmProvider.models), selectinload(LlmProvider.channels))
            .order_by(LlmProvider.sort, LlmProvider.id)
            .all()
        )
        router = self._router()  # 复用一个 router，避免每个 provider 重建
        return [self._provider_dict(p, router) for p in rows]

    def create_provider(self, req, user: Account) -> dict:
        self._assert_llm_admin_enabled()
        exists = db.session.query(LlmProvider.id).filter(LlmProvider.name == req.name).first()
        if exists:
            raise ValidateErrorException(message=f"提供商标识已存在：{req.name}")
        self._check_protocol(req.protocol)
        row = LlmProvider(
            name=req.name,
            label=req.label or {},
            description=req.description or {},
            icon=req.icon or "",
            background=req.background or "",
            supported_model_types=req.supported_model_types or ["chat"],
            protocol=req.protocol or "openai",
            multi_channel=bool(req.multi_channel),
            base_url=req.base_url or "",
            api_key_cipher=crypto.encrypt(req.api_key) if req.api_key else "",
            api_key_env=req.api_key_env or "",
            enabled=bool(req.enabled),
            sort=int(req.sort or 0),
        )
        with db.auto_commit():
            db.session.add(row)
        db.session.refresh(row)
        self.manager.bump_version()
        return self._provider_dict(row)

    def update_provider(self, provider_id: int, req, user: Account) -> dict:
        self._assert_llm_admin_enabled()
        row = self._get(LlmProvider, provider_id, "提供商")
        data = req.model_dump(exclude_unset=True)
        if "protocol" in data and data["protocol"]:
            self._check_protocol(data["protocol"])
        with db.auto_commit():
            self._apply(row, data, (
                "label", "description", "icon", "background", "supported_model_types",
                "protocol", "multi_channel", "base_url", "api_key_env", "enabled", "sort",
            ))
            # api_key 仅在传入非空时覆盖（空/缺省=保留原密钥）
            if data.get("api_key"):
                row.api_key_cipher = crypto.encrypt(data["api_key"])
        db.session.refresh(row)
        self.manager.bump_version()
        return self._provider_dict(row)

    def delete_provider(self, provider_id: int, user: Account) -> None:
        self._assert_llm_admin_enabled()
        row = self._get(LlmProvider, provider_id, "提供商")
        with db.auto_commit():
            db.session.delete(row)  # FK CASCADE 连带删 model / channel
        self.manager.bump_version()

    # ---------------- model ----------------

    def create_model(self, provider_id: int, req, user: Account) -> dict:
        self._assert_llm_admin_enabled()
        self._get(LlmProvider, provider_id, "提供商")
        dup = db.session.query(LlmModel.id).filter(
            LlmModel.provider_id == provider_id, LlmModel.model_name == req.model_name,
        ).first()
        if dup:
            raise ValidateErrorException(message=f"该提供商下已存在模型：{req.model_name}")
        row = LlmModel(
            provider_id=provider_id,
            model_name=req.model_name,
            label=req.label or {},
            model_type=req.model_type or "chat",
            features=req.features or [],
            context_window=int(req.context_window or 4096),
            max_output_tokens=req.max_output_tokens,
            parameter_rules=req.parameter_rules or [],
            pricing=req.pricing,
            deprecated=bool(req.deprecated),
            admin_only=bool(req.admin_only),
            is_default=bool(req.is_default),
            enabled=bool(req.enabled),
            sort=int(req.sort or 0),
        )
        with db.auto_commit():
            db.session.add(row)
            if row.is_default:
                self._clear_other_defaults(provider_id, row, row.model_type)
        db.session.refresh(row)
        self.manager.bump_version()
        return self._model_dict(row)

    def update_model(self, model_id: int, req, user: Account) -> dict:
        self._assert_llm_admin_enabled()
        row = self._get(LlmModel, model_id, "模型")
        data = req.model_dump(exclude_unset=True)
        if data.get("model_name") and data["model_name"] != row.model_name:
            dup = db.session.query(LlmModel.id).filter(
                LlmModel.provider_id == row.provider_id,
                LlmModel.model_name == data["model_name"],
                LlmModel.id != row.id,
            ).first()
            if dup:
                raise ValidateErrorException(message=f"该提供商下已存在模型：{data['model_name']}")
        with db.auto_commit():
            self._apply(row, data, (
                "model_name", "label", "model_type", "features", "context_window",
                "max_output_tokens", "parameter_rules", "pricing", "deprecated",
                "admin_only", "is_default", "enabled", "sort",
            ))
            if row.is_default:
                self._clear_other_defaults(row.provider_id, row, row.model_type)
        db.session.refresh(row)
        self.manager.bump_version()
        return self._model_dict(row)

    def delete_model(self, model_id: int, user: Account) -> None:
        self._assert_llm_admin_enabled()
        row = self._get(LlmModel, model_id, "模型")
        with db.auto_commit():
            db.session.delete(row)
        self.manager.bump_version()

    @staticmethod
    def _clear_other_defaults(provider_id: int, keep: LlmModel, model_type: str) -> None:
        """同一 provider 同一类型最多一个 is_default：把其它的清掉。"""
        others = db.session.query(LlmModel).filter(
            LlmModel.provider_id == provider_id,
            LlmModel.model_type == model_type,
            LlmModel.is_default.is_(True),
        ).all()
        for o in others:
            if o.id != keep.id:
                o.is_default = False

    # ---------------- channel ----------------

    def list_channels(self, provider_id: int, user: Account) -> list[dict]:
        self._assert_llm_admin_enabled()
        self._get(LlmProvider, provider_id, "提供商")
        rows = db.session.query(LlmChannel).filter(
            LlmChannel.provider_id == provider_id,
        ).order_by(LlmChannel.priority, LlmChannel.id).all()
        router = self._router()
        return [self._channel_dict(c, router) for c in rows]

    def create_channel(self, provider_id: int, req, user: Account) -> dict:
        self._assert_llm_admin_enabled()
        provider = self._get(LlmProvider, provider_id, "提供商")
        if not provider.multi_channel:
            raise ValidateErrorException(message="该提供商未开启多渠道，无法添加渠道")
        row = LlmChannel(
            provider_id=provider_id,
            name=req.name or "",
            base_url=req.base_url,
            api_key_cipher=crypto.encrypt(req.api_key) if req.api_key else "",
            priority=int(req.priority or 0),
            models=req.models or [],
            enabled=bool(req.enabled),
        )
        with db.auto_commit():
            db.session.add(row)
        db.session.refresh(row)
        self.manager.bump_version()
        return self._channel_dict(row, self._router())

    def update_channel(self, channel_id: int, req, user: Account) -> dict:
        self._assert_llm_admin_enabled()
        row = self._get(LlmChannel, channel_id, "渠道")
        data = req.model_dump(exclude_unset=True)
        with db.auto_commit():
            self._apply(row, data, ("name", "base_url", "priority", "models", "enabled"))
            if data.get("api_key"):
                row.api_key_cipher = crypto.encrypt(data["api_key"])
        db.session.refresh(row)
        self.manager.bump_version()
        return self._channel_dict(row, self._router())

    def delete_channel(self, channel_id: int, user: Account) -> None:
        self._assert_llm_admin_enabled()
        row = self._get(LlmChannel, channel_id, "渠道")
        cid = row.id
        with db.auto_commit():
            db.session.delete(row)
        self._router().recover(cid)  # 顺手清掉它的熔断 redis key
        self.manager.bump_version()

    def recover_channel(self, channel_id: int, user: Account) -> None:
        """手动恢复：清掉该渠道的熔断 / 失败计数 redis key。"""
        self._assert_llm_admin_enabled()
        row = self._get(LlmChannel, channel_id, "渠道")
        self._router().recover(row.id)

    # ---------------- 内部 ----------------

    @staticmethod
    def _check_protocol(protocol: str) -> None:
        if protocol and protocol not in list_protocols():
            raise ValidateErrorException(
                message=f"协议不支持：{protocol}（可选：{', '.join(list_protocols())}）"
            )

    @staticmethod
    def _key_display(cipher: str, api_key_env: str = "") -> tuple[bool, str]:
        """返回 (是否已配 key, 掩码展示)。密文优先；否则回落 env 变量名提示。"""
        if cipher:
            return True, crypto.mask(crypto.decrypt(cipher))
        if api_key_env:
            return False, f"(环境变量 {api_key_env})"
        return False, ""

    def _provider_dict(self, p: LlmProvider, router: ChannelRouter = None) -> dict:
        has_key, mask = self._key_display(p.api_key_cipher, p.api_key_env)
        d = {
            "id": p.id,
            "name": p.name,
            "label": p.label or {},
            "description": p.description or {},
            "icon": p.icon or "",
            "background": p.background or "",
            "supported_model_types": p.supported_model_types or [],
            "protocol": p.protocol,
            "multi_channel": bool(p.multi_channel),
            "base_url": p.base_url or "",
            "has_api_key": has_key,
            "api_key_mask": mask,
            "api_key_env": p.api_key_env or "",
            "enabled": bool(p.enabled),
            "sort": p.sort,
            "models": [self._model_dict(m) for m in p.models],
        }
        if p.multi_channel:
            router = router or self._router()
            d["channels"] = [self._channel_dict(c, router) for c in p.channels]
        return d

    @staticmethod
    def _model_dict(m: LlmModel) -> dict:
        return {
            "id": m.id,
            "provider_id": m.provider_id,
            "model_name": m.model_name,
            "label": m.label or {},
            "model_type": m.model_type,
            "features": m.features or [],
            "context_window": m.context_window,
            "max_output_tokens": m.max_output_tokens,
            "parameter_rules": m.parameter_rules or [],
            "pricing": m.pricing,
            "deprecated": bool(m.deprecated),
            "admin_only": bool(m.admin_only),
            "is_default": bool(m.is_default),
            "enabled": bool(m.enabled),
            "sort": m.sort,
        }

    def _channel_dict(self, c: LlmChannel, router: ChannelRouter) -> dict:
        has_key, mask = self._key_display(c.api_key_cipher, "")
        return {
            "id": c.id,
            "provider_id": c.provider_id,
            "name": c.name or "",
            "base_url": c.base_url or "",
            "has_api_key": has_key,
            "api_key_mask": mask,
            "priority": c.priority,
            "models": c.models or [],
            "enabled": bool(c.enabled),
            "health": router.health(c.id),
        }
