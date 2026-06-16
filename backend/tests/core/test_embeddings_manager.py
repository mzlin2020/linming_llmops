"""EmbeddingsManager：向量维 / token 计数 / 假替身（均不加载 torch）。"""
import sys

from internal.core.embeddings.embeddings_manager import EmbeddingsManager


def test_vector_size_default_and_env(monkeypatch):
    em = EmbeddingsManager()
    monkeypatch.delenv("EMBEDDING_VECTOR_SIZE", raising=False)
    assert em.vector_size == 512
    monkeypatch.setenv("EMBEDDING_VECTOR_SIZE", "1024")
    assert em.vector_size == 1024
    monkeypatch.setenv("EMBEDDING_VECTOR_SIZE", "not-an-int")
    assert em.vector_size == 512  # 非法 → 回落 512


def test_calculate_token_count():
    n = EmbeddingsManager.calculate_token_count("hello world")
    assert isinstance(n, int) and n >= 1
    assert EmbeddingsManager.calculate_token_count("") == 0


def test_importing_module_does_not_load_torch():
    # 出口铁律：embedding 模块导入不得触发重型栈（懒加载在 property 内）。
    assert "torch" not in sys.modules


def test_fake_embeddings_fixture_deterministic(fake_embeddings):
    em = EmbeddingsManager()
    assert em.vector_size == 8
    v1 = em.embeddings.embed_query("abc")
    v2 = em.embeddings.embed_query("abc")
    assert len(v1) == 8 and v1 == v2          # 同文本 → 同向量
    assert em.embeddings.embed_query("xyz") != v1
    assert "torch" not in sys.modules
