"""StorageService：存储门面（DI 注入点）。按 STORAGE_BACKEND 选后端，业务层只依赖本服务。

v1 仅实现 local；s3/minio 留接口位（配置切到这些后端时显式报 NotImplementedError，
等后续阶段补对象存储实现）。后端按调用时配置惰性构建（便于测试 monkeypatch STORAGE_ROOT）。
"""
from dataclasses import dataclass, field

from flask import current_app
from injector import inject

from internal.storage.base import BaseStorage
from internal.storage.local import LocalStorage


@inject
@dataclass
class StorageService:
    # 缓存 (配置, 后端实例)，仅当 STORAGE_BACKEND/STORAGE_ROOT 变化才重建——
    # 避免每次调用都重跑 LocalStorage 的 abspath+makedirs；测试 monkeypatch STORAGE_ROOT 后 key 变化会自动重建。
    _cached: tuple = field(default=None, init=False, repr=False)

    def save(self, key: str, data: bytes) -> None:
        self._backend().save(key, data)

    def load(self, key: str) -> bytes:
        return self._backend().load(key)

    def delete(self, key: str) -> None:
        self._backend().delete(key)

    def exists(self, key: str) -> bool:
        return self._backend().exists(key)

    def local_path(self, key: str) -> str:
        return self._backend().local_path(key)

    # ---------- internal ----------

    def _backend(self) -> BaseStorage:
        backend = (current_app.config.get("STORAGE_BACKEND") or "local").lower()
        root = current_app.config.get("STORAGE_ROOT") or "storage"
        if self._cached is not None and self._cached[0] == (backend, root):
            return self._cached[1]
        if backend == "local":
            inst = LocalStorage(root)
        else:
            raise NotImplementedError(
                f"存储后端 {backend} 暂未实现（v1 仅支持 local，S3/MinIO 后续阶段补充）"
            )
        self._cached = ((backend, root), inst)
        return inst
