"""ImageGenerationService：文生图 / 图生图。

三件事：①配额安全网（check_image_generation，纯防爆量花钱）；②调已配置的生图模型
（OpenAI 兼容 /images/generations，由 LanguageModelManager.generate_images 发出）；
③把上游返回的图片（url 或 b64_json）落到 StorageService，按「能力 URL」对外提供，
落 ai_image 表，返回记录 dict。

provider/model 由请求指定（编排页/生图页下拉），缺省回落 DEFAULT_IMAGE_PROVIDER/MODEL；
二者皆空则友好报错（默认未配置即等于关闭，优雅降级）。被独立生图接口与内置工具（Agent 画图）共用。

访问控制：本平台为自托管轻量登录、无管理员概念，图像生成对所有登录用户开放；成本由
QUOTA_IMAGE_DAILY_LIMIT（每日上限，<=0 即不限）兜底。图片走不可猜的 uuid 能力 URL
（/api/images/file/<uuid>.<ext>，无需登录即可由 <img> 加载），等价于公网对象存储的预签名 URL 模型。
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from flask import current_app
from injector import inject

from internal.core.language_model import LanguageModelManager
from internal.exception import FailException
from internal.extension.database_extension import db
from internal.model import AiImage
from internal.service.quota_service import QuotaService
from internal.storage import StorageService
from pkg.paginator import Paginator

# MIME ↔ 扩展名（落地文件名带 ext，能力 URL 读取时据此回推 MIME，无需查库）
_MIME_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}
_EXT_MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}
# 能力 URL 文件名：32 位 uuid4.hex + 白名单扩展名（拒一切路径穿越 / 非法字符）
_FILE_NAME_RE = re.compile(r"^[0-9a-f]{32}\.(png|jpg|jpeg|webp|gif)$")
_STORAGE_PREFIX = "image_gen"


@inject
@dataclass
class ImageGenerationService:
    language_model_manager: LanguageModelManager
    quota_service: QuotaService
    storage_service: StorageService

    # ---------------- 对外入口 ----------------

    def text_to_image(self, user, req) -> dict:
        self.quota_service.check_image_generation(user)
        return self._generate(
            user, prompt=req.prompt, provider=req.provider, model=req.model,
            size=req.size, guidance_scale=req.guidance_scale, image=None,
        )

    def image_to_image(self, user, req) -> dict:
        # 参考图 URL 必须在白名单域名内 + 过 SSRF 守卫（复用聊天附件那套校验）
        from internal.service._chat_attachments import assert_url_allowed
        assert_url_allowed(req.image_url)
        self.quota_service.check_image_generation(user)
        return self._generate(
            user, prompt=req.prompt, provider=req.provider, model=req.model,
            size=req.size, guidance_scale=req.guidance_scale, image=req.image_url,
        )

    def list_images(self, user, current_page: int, page_size: int) -> dict:
        """生图历史（画廊），按本人 user_id 归属过滤。"""
        query = db.session.query(AiImage).filter(AiImage.user_id == user.id)
        paginator = Paginator(page=current_page, page_size=page_size, total_record=query.count())
        rows = query.order_by(AiImage.id.desc()).offset(paginator.offset).limit(page_size).all()
        paginator.items = [self._to_dict(r) for r in rows]
        return paginator.to_dict()

    def read_image_file(self, name: str) -> Optional[tuple[bytes, str]]:
        """能力 URL 读取：name 须为 <uuid>.<ext>（拒路径穿越）；返回 (bytes, mime) 或 None。"""
        if not _FILE_NAME_RE.match(name or ""):
            return None
        ext = name.rsplit(".", 1)[-1]
        try:
            data = self.storage_service.load(f"{_STORAGE_PREFIX}/{name}")
        except (FileNotFoundError, OSError):
            return None
        return data, _EXT_MIME.get(ext, "application/octet-stream")

    # ---------------- internal ----------------

    def _resolve_provider_model(self, provider, model) -> tuple[str, str]:
        cfg = current_app.config
        provider = (provider or cfg.get("DEFAULT_IMAGE_PROVIDER") or "").strip()
        model = (model or cfg.get("DEFAULT_IMAGE_MODEL") or "").strip()
        if not provider or not model:
            raise FailException(
                message="未配置生图模型，请先在部署环境设置 DEFAULT_IMAGE_PROVIDER / DEFAULT_IMAGE_MODEL"
            )
        return provider, model

    def _generate(self, user, *, prompt: str, provider, model, size, guidance_scale, image) -> dict:
        # 传了参考图即图生图，否则文生图——类型与输入图 URL 都从 image 派生
        gen_type = "img2img" if image else "text2img"
        provider, model = self._resolve_provider_model(provider, model)
        # 只透传用户显式给的可选参数（保持对 OpenAI 兼容端点的最小请求体；厂商扩展由调用方按需带入）
        params: dict = {}
        if size:
            params["size"] = size
        if guidance_scale is not None:
            params["guidance_scale"] = guidance_scale

        try:
            data = self.language_model_manager.generate_images(provider, model, prompt, image=image, **params)
        except Exception as e:  # 上游 HTTP / 网络异常统一转站内错误信封
            raise FailException(message=f"图像生成失败：{str(e)[:160]}")

        data0 = (data[0] if data else None) or {}
        img_bytes, mime, ext = self._fetch_image(data0.get("url"), data0.get("b64_json"))

        name = f"{uuid4().hex}.{ext}"
        self.storage_service.save(f"{_STORAGE_PREFIX}/{name}", img_bytes)

        record = AiImage(
            user_id=user.id,
            type=gen_type,
            provider=provider,
            model=model,
            prompt=prompt,
            size=size or "",
            input_image_url=image or "",
            url=f"/api/images/file/{name}",
            mime_type=mime,
            size_bytes=len(img_bytes),
        )
        with db.auto_commit():
            db.session.add(record)
        db.session.refresh(record)
        return self._to_dict(record)

    def _fetch_image(self, src_url, b64) -> tuple[bytes, str, str]:
        """把上游图片取成字节：优先下载 url（运维自配的可信 base_url），否则解 b64_json。"""
        try:
            if src_url:
                import requests

                resp = requests.get(src_url, timeout=60)
                resp.raise_for_status()
                data = resp.content
                mime = (resp.headers.get("Content-Type", "") or "").split(";")[0].strip().lower() or "image/png"
            elif b64:
                data = base64.b64decode(b64)
                mime = "image/png"
            else:
                raise FailException(message="图像生成失败：上游未返回图片")
        except FailException:
            raise
        except Exception as e:
            raise FailException(message=f"图像生成失败：取回图片出错（{str(e)[:120]}）")
        return data, mime, _MIME_EXT.get(mime, "png")

    @staticmethod
    def _to_dict(record: AiImage) -> dict:
        return {
            "id": record.id,
            "type": record.type,
            "provider": record.provider,
            "model": record.model,
            "prompt": record.prompt,
            "size": record.size,
            "input_image_url": record.input_image_url,
            "url": record.url,
            "created_at": int(record.created_at.timestamp()) if record.created_at else 0,
        }
