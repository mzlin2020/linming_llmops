"""存储适配器：LocalStorage 经 StorageService 的存取/删除往返，以及未知后端报错。纯本机（无 redis/qdrant）。"""
import pytest

from internal.storage import StorageService


def test_local_storage_roundtrip(app_context, tmp_path, monkeypatch):
    monkeypatch.setitem(app_context.config, "STORAGE_BACKEND", "local")
    monkeypatch.setitem(app_context.config, "STORAGE_ROOT", str(tmp_path))
    svc = StorageService()
    key = "upload/1/abc.txt"

    assert svc.exists(key) is False
    svc.save(key, b"hello world")
    assert svc.exists(key) is True
    assert svc.load(key) == b"hello world"
    assert svc.local_path(key) == str(tmp_path / "upload" / "1" / "abc.txt")

    svc.delete(key)
    assert svc.exists(key) is False
    # 删除不存在的 key 不报错
    svc.delete(key)


def test_unknown_backend_raises(app_context, monkeypatch):
    monkeypatch.setitem(app_context.config, "STORAGE_BACKEND", "s3")
    with pytest.raises(NotImplementedError):
        StorageService().save("k", b"x")
