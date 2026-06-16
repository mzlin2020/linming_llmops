"""AI 聊天附件处理：URL 白名单 / 数量与类型校验 / 文档下载抽取 / 多模态判定的小工具。

被 chat_service / assistant_agent_service（openapi 复用 chat 内核）几条链路共用。
附件先由前端经上传接口落存储，这里只收 URL：
- 图片（jpg/jpeg/png/gif/webp）→ 多模态 image_url parts，要求模型带 vision；
- 文档（file_extractor 支持的扩展名）→ 下载到临时文件抽取文本注入 LLM，任何模型可用。
所有校验在 view 上下文执行（进 SSE 前），违例抛 ValidateErrorException → 标准错误信封。
"""
from __future__ import annotations

import os
import tempfile
from urllib.parse import unquote, urlparse

from flask import current_app

from internal.core.file_extractor import is_supported as _doc_supported
from internal.core.file_extractor import load_text as _doc_load_text
from internal.core.tools.api_tools.providers._safe_http import (
    UnsafeRequestError,
    assert_safe_url,
    safe_request,
)
from internal.exception import ValidateErrorException

# 图片扩展名白名单（与上传端、前端预检对齐）
IMAGE_EXTS = frozenset({"jpg", "jpeg", "png", "gif", "webp"})


def _allowed_prefixes() -> list[str]:
    raw = current_app.config.get("CHAT_ATTACHMENT_URL_PREFIXES", "") or ""
    return [p.strip() for p in raw.split(",") if p.strip()]


def _assert_prefix_allowed(url: str) -> None:
    if not any(url.startswith(p) for p in _allowed_prefixes()):
        raise ValidateErrorException(message="附件地址不在允许的域名白名单内")


def assert_url_allowed(url: str) -> None:
    """白名单前缀 + SSRF 守卫（assert_safe_url），两者皆过才放行。"""
    _assert_prefix_allowed(url)
    try:
        assert_safe_url(url)
    except UnsafeRequestError as e:
        raise ValidateErrorException(message=f"附件地址校验失败：{e}")


def ext_of(url: str) -> str:
    """URL path 的小写扩展名（不带点）；无扩展名返回空串。"""
    path = urlparse(url).path
    return path.rsplit(".", 1)[-1].lower() if "." in path else ""


def name_of(url: str) -> str:
    """URL path 的文件名（decode 后），落 file_infos 给前端展示用。"""
    path = unquote(urlparse(url).path)
    return path.rsplit("/", 1)[-1] or "文件"


def validate_attachments(image_urls: list[str], file_urls: list[str]) -> None:
    """数量上限 + 逐个 URL 白名单/SSRF + 扩展名类型校验。违例抛 422。"""
    max_img = int(current_app.config.get("CHAT_MAX_IMAGES_PER_MESSAGE", 3))
    max_doc = int(current_app.config.get("CHAT_MAX_FILES_PER_MESSAGE", 2))
    if len(image_urls) > max_img:
        raise ValidateErrorException(message=f"单条消息图片不能超过 {max_img} 张")
    if len(file_urls) > max_doc:
        raise ValidateErrorException(message=f"单条消息文档不能超过 {max_doc} 个")
    for u in image_urls:
        assert_url_allowed(u)
        if ext_of(u) not in IMAGE_EXTS:
            raise ValidateErrorException(message="图片类型不支持（仅 jpg/jpeg/png/gif/webp）")
    for u in file_urls:
        assert_url_allowed(u)
        if not _doc_supported(ext_of(u)):
            raise ValidateErrorException(message="文档类型不支持")


def extract_file_text(url: str) -> str:
    """下载文档到临时文件 → file_extractor 抽取文本 → 截断。

    抽取结果由调用方缓存进 ai_message.file_infos（一次抽取，历史回放免重复下载）。
    任何失败统一抛 ValidateErrorException（view 上下文，进 SSE 前）。"""
    # 二次守卫只查前缀（即使调用方漏 validate 也不放行白名单外 URL）；
    # SSRF 的 DNS 校验交给下面 safe_request 内部那次，避免一次下载做 3 遍 getaddrinfo
    _assert_prefix_allowed(url)
    ext = ext_of(url)
    max_bytes = int(current_app.config.get("CHAT_DOC_DOWNLOAD_MAX_BYTES", 10485760))
    max_chars = int(current_app.config.get("CHAT_DOC_TEXT_MAX_CHARS", 20000))
    tmp_path = None
    try:
        resp = safe_request("GET", url, stream=True)
        resp.raise_for_status()
        total = 0
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tf:
            tmp_path = tf.name
            for chunk in resp.iter_content(8192):
                total += len(chunk)
                if total > max_bytes:
                    raise ValidateErrorException(message="文档体积过大")
                tf.write(chunk)
        text = _doc_load_text(tmp_path, ext) or ""
        return text[:max_chars]
    except ValidateErrorException:
        raise
    except Exception as e:
        raise ValidateErrorException(message=f"文档解析失败：{str(e)[:100]}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def build_file_infos(file_urls: list[str]) -> list[dict]:
    """file_urls → [{url, name, extension, text}]，text 为截断后的抽取缓存。"""
    return [
        {"url": u, "name": name_of(u), "extension": ext_of(u), "text": extract_file_text(u)}
        for u in file_urls
    ]


def prepare_attachments(
    llm_manager, quota_service, user, req, provider: str, model_name: str,
) -> tuple[list[str], list[dict], bool]:
    """附件前置（view 上下文，进 SSE 前），chat / assistant-agent 两条链路共用：
    vision 兜底校验 → URL/类型/数量校验 → 配额记账 → 文档下载抽取。
    返回 (image_urls, file_infos, vision_ok)。"""
    image_urls = list(getattr(req, "image_urls", None) or [])
    file_urls = list(getattr(req, "file_urls", None) or [])
    vision_ok = llm_manager.supports_vision(provider, model_name)
    if image_urls and not vision_ok:
        raise ValidateErrorException(message="当前模型不支持图片理解，请切换到支持图片的模型")
    if not image_urls and not file_urls:
        return [], [], vision_ok
    validate_attachments(image_urls, file_urls)
    quota_service.check_chat_attachment(user, len(image_urls) + len(file_urls))
    return image_urls, build_file_infos(file_urls), vision_ok
