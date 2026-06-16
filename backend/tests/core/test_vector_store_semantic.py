"""向量库 + 语义检索（需真实 Qdrant；本机无 Qdrant 自动 skip，CI 有 service 容器跑）。

用 fake_embeddings（8 维确定性向量）写入 → SemanticRetriever 检索 → 命中同文本片段（cosine≈1）。
"""
import uuid


def test_upsert_and_semantic_search(app_context, fake_embeddings, qdrant_client_or_skip, kb_collection):
    from internal.core.embeddings.embeddings_manager import EmbeddingsManager
    from internal.core.retrievers import SemanticRetriever
    from internal.core.vector_store import qdrant_vector_store as vs

    em = EmbeddingsManager()
    dim = em.vector_size  # 8（被 fake_embeddings 打桩）
    vs.ensure_dataset_collection(dim)

    texts = ["Python 是一门编程语言", "今天天气晴朗", "向量检索很有用"]
    points = []
    for i, txt in enumerate(texts, start=1):
        vec = em.embeddings.embed_documents([txt])[0]
        payload = vs.build_payload(
            text=txt, dataset_id=1, document_id=1, segment_id=i,
            document_enabled=True, segment_enabled=True,
        )
        points.append(vs.make_point(str(uuid.uuid4()), vec, payload))
    vs.upsert_points(points)

    retr = SemanticRetriever(dataset_ids=[1], embeddings=em.embeddings, k=2, score=0.0)
    docs = retr.invoke("Python 是一门编程语言")
    assert docs, "应至少召回一条"
    # 同文本向量 cosine=1，排第一。
    assert docs[0].page_content == "Python 是一门编程语言"
    assert docs[0].metadata["dataset_id"] == 1


def test_disabled_segment_filtered_out(app_context, fake_embeddings, qdrant_client_or_skip, kb_collection):
    from internal.core.embeddings.embeddings_manager import EmbeddingsManager
    from internal.core.retrievers import SemanticRetriever
    from internal.core.vector_store import qdrant_vector_store as vs

    em = EmbeddingsManager()
    vs.ensure_dataset_collection(em.vector_size)

    txt = "被禁用的片段不应被检索到"
    vec = em.embeddings.embed_documents([txt])[0]
    payload = vs.build_payload(
        text=txt, dataset_id=2, document_id=1, segment_id=1,
        document_enabled=True, segment_enabled=False,   # 片段禁用
    )
    vs.upsert_points([vs.make_point(str(uuid.uuid4()), vec, payload)])

    retr = SemanticRetriever(dataset_ids=[2], embeddings=em.embeddings, k=4)
    assert retr.invoke(txt) == []
