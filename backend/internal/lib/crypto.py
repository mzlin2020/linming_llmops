"""对称加密小工具：把 AI 模型提供商 / 渠道的 API Key 加密后落库。

基于已在依赖里的 cryptography(Fernet)。密钥材料取环境变量 AI_SECRET_ENCRYPT_KEY，
缺省回落 JWT_SECRET，派生为 Fernet 需要的 32 字节 urlsafe-base64 key。

约定：
- encrypt("") / encrypt(None) → ""（空不加密，便于「不修改 key」时存空）。
- decrypt 对空 / 非法 / 换过密钥导致解不开的密文一律返回 ""（容错，绝不抛，免得拖垮聊天热路径）。
- 密钥材料丢失 → 历史密文不可解（需在后台重填 key）。.env 注释里已写明这是密钥材料、勿轻易更换。
"""
import base64
import hashlib
import os

from cryptography.fernet import Fernet


def _secret() -> str:
    return os.getenv("AI_SECRET_ENCRYPT_KEY") or os.getenv("JWT_SECRET") or ""


# 按 secret 值缓存 Fernet 实例（secret 变了自然换一把）；不在模块级固化，便于测试切 env。
_FERNET_CACHE: dict[str, Fernet] = {}


def _fernet() -> Fernet:
    secret = _secret()
    f = _FERNET_CACHE.get(secret)
    if f is None:
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
        f = Fernet(key)
        _FERNET_CACHE[secret] = f
    return f


def encrypt(plain: str) -> str:
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt(cipher: str) -> str:
    if not cipher:
        return ""
    try:
        return _fernet().decrypt(cipher.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


def mask(plain: str) -> str:
    """把明文密钥脱敏成展示用字符串：保留尾 4 位，如 'sk-***1234'。空 → ''。"""
    if not plain:
        return ""
    tail = plain[-4:] if len(plain) >= 4 else plain
    return f"***{tail}"
