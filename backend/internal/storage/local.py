"""LocalStorage：本地磁盘存储后端（v1 默认）。

root 为存储根目录（相对路径自动转绝对，并 makedirs）；key 为相对 root 的路径。
容器部署时把 root 挂载到数据卷即可持久化。
"""
import os

from internal.storage.base import BaseStorage


class LocalStorage(BaseStorage):
    def __init__(self, root: str):
        if not os.path.isabs(root):
            root = os.path.abspath(root)
        os.makedirs(root, exist_ok=True)
        self._root = root

    def save(self, key: str, data: bytes) -> None:
        path = self.local_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

    def load(self, key: str) -> bytes:
        with open(self.local_path(key), "rb") as f:
            return f.read()

    def delete(self, key: str) -> None:
        try:
            os.remove(self.local_path(key))
        except FileNotFoundError:
            pass

    def exists(self, key: str) -> bool:
        return os.path.isfile(self.local_path(key))

    def local_path(self, key: str) -> str:
        return os.path.join(self._root, key)
