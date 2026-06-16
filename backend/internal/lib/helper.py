import hashlib
import importlib
import secrets
import string
from datetime import datetime
from typing import Any, Optional

from pydantic import ValidationError


def generate_random_string(length: int = 16) -> str:
    """生成定长的安全随机串（小写字母 + 数字），用于发布应用的访问凭证 token。"""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_text_hash(text: str) -> str:
    """文本内容的 sha256 十六进制摘要（判断片段内容是否变化、是否需重建向量）。"""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def first_validation_error(e: ValidationError) -> str:
    """pydantic v2 校验错误 → 首条人读消息（供 ValidateErrorException）。"""
    errors = e.errors()
    return str(errors[0].get("msg", "参数错误")) if errors else "参数错误"


def datetime_to_timestamp(dt: Optional[datetime]) -> Optional[int]:
    if dt is None:
        return None
    return int(dt.timestamp() * 1000)


def dedupe_copy_name(base: str, existing: set, max_len: int = 64) -> str:
    """在 existing 名字集合内算出不冲突的名字：base → base-副本 → base-副本2…，截断到 max_len。
    商店「添加到我的」复制场景共用（插件商店 / 应用商店）。"""
    if base not in existing:
        return base
    for i in range(1, 1000):
        suffix = "-副本" if i == 1 else f"-副本{i}"
        candidate = base[: max_len - len(suffix)] + suffix
        if candidate not in existing:
            return candidate
    return base[: max_len - 4] + "-副本x"  # 兜底，几乎不可达


def dynamic_import(module_name: str, symbol_name: str) -> Any:
    """动态导入特定模块下的特定符号（工具工厂、provider 包等运行期按名取用）。"""
    module = importlib.import_module(module_name)
    return getattr(module, symbol_name)


def add_attribute(attr_name: str, attr_value: Any):
    """装饰器：给被装饰的函数挂一个属性。

    内置工具用它把 args_schema 挂到工具工厂函数上，这样无需实例化工具即可读出入参 schema。
    """

    def decorator(func):
        setattr(func, attr_name, attr_value)
        return func

    return decorator
