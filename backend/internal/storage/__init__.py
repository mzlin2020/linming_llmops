"""存储适配器：把上传文件落地从具体后端（本地磁盘 / 对象存储）解耦。"""
from .base import BaseStorage
from .local import LocalStorage
from .storage_service import StorageService

__all__ = ["BaseStorage", "LocalStorage", "StorageService"]
