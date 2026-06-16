"""Phase 3 核心层测试夹具：假 embedding（不加载 torch）+ Qdrant 连通性跳过守卫。"""
import uuid

import pytest

_FAKE_EMBED_DIM = 8


class _FakeEmbeddings:
    """确定性假 embedding：同一文本→同一向量（query==某片段文本时 cosine=1，命中该片段）。
    维度固定 _FAKE_EMBED_DIM，避免单测加载真实嵌入模型（torch/sentence-transformers）。"""

    @staticmethod
    def _vec(text):
        import hashlib
        digest = hashlib.sha256((text or "").encode("utf-8")).digest()
        return [digest[i % len(digest)] / 255.0 for i in range(_FAKE_EMBED_DIM)]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


@pytest.fixture
def fake_embeddings(monkeypatch):
    """把 EmbeddingsManager.embeddings / vector_size 换成假实现（不加载真实模型）。"""
    from internal.core.embeddings.embeddings_manager import EmbeddingsManager

    fake = _FakeEmbeddings()
    monkeypatch.setattr(EmbeddingsManager, "embeddings", property(lambda self: fake))
    monkeypatch.setattr(EmbeddingsManager, "vector_size", property(lambda self: _FAKE_EMBED_DIM))
    return fake


@pytest.fixture
def openai_provider(app_context, db_tables):
    """播一条启用的 openai/gpt-4o-mini provider+model（含加密 key），用完即删。

    db_tables 是 session 级、表跨用例存活，故必须逐用例清理避免相互污染；
    放进夹具 teardown 比每个用例手写 delete 更稳。
    """
    from internal.extension.database_extension import db
    from internal.lib import crypto
    from internal.model import LlmModel, LlmProvider

    prov = LlmProvider(
        name="openai", protocol="openai",
        api_key_cipher=crypto.encrypt("sk-test"),
        base_url="https://api.example.com/v1", enabled=True,
    )
    db.session.add(prov)
    db.session.flush()
    db.session.add(LlmModel(
        provider_id=prov.id, model_name="gpt-4o-mini", model_type="chat",
        features=["tool_call"],
        pricing={"input": 1.0, "output": 2.0, "unit": "0.001", "currency": "USD"},
        enabled=True,
    ))
    db.session.commit()
    yield prov
    db.session.delete(prov)   # FK ondelete=cascade 连带删 LlmModel
    db.session.commit()


@pytest.fixture
def qdrant_client_or_skip(app):
    """返回可用的 Qdrant client；连不上则 skip（本机沙箱无 Qdrant，CI 有 service 容器）。"""
    from internal.core.vector_store.qdrant_vector_store import get_qdrant_client

    with app.app_context():
        try:
            client = get_qdrant_client()
            client.get_collections()
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"Qdrant 不可用，跳过（交 CI 跑）：{exc}")
        return client


@pytest.fixture
def kb_collection(monkeypatch):
    """给知识库用一个独立的临时 Qdrant collection（测试维度 8），用完即删，避免污染真实 ai_dataset。"""
    name = f"ai_dataset_test_{uuid.uuid4().hex[:8]}"
    monkeypatch.setenv("QDRANT_DATASET_COLLECTION", name)
    yield name
    try:
        from internal.core.vector_store.qdrant_vector_store import get_qdrant_client
        client = get_qdrant_client()
        if client.collection_exists(name):
            client.delete_collection(name)
    except Exception:
        pass
