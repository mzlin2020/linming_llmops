"""存储后端抽象接口：把「文件字节存到哪、怎么取」从业务层解耦。

v1 默认 LocalStorage（本地磁盘），接口预留 S3/MinIO 等对象存储后端切换（self-hosted 友好，
不依赖任何外部网关）。key 为相对路径（如 upload/<user_id>/<uuid>.<ext>），由调用方生成。
"""
from abc import ABC, abstractmethod


class BaseStorage(ABC):
    """存储后端协议：实现方负责把 key→字节 的读写/删除/定位。"""

    @abstractmethod
    def save(self, key: str, data: bytes) -> None:
        """把 data 字节写到 key 指向的位置（覆盖式）。"""

    @abstractmethod
    def load(self, key: str) -> bytes:
        """读取 key 的全部字节。"""

    @abstractmethod
    def delete(self, key: str) -> None:
        """删除 key（不存在时静默）。"""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """key 是否存在。"""

    @abstractmethod
    def local_path(self, key: str) -> str:
        """返回 key 对应的本地可读路径（文档解析需要本地文件路径）。

        本地后端直接返回磁盘绝对路径；对象存储后端实现时需下载到临时文件再返回其路径。
        """
