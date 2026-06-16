"""Qdrant 集成。

知识库片段统一住**一个**共享 collection（默认 `ai_dataset`，名取 env QDRANT_DATASET_COLLECTION），
`dataset_id` 进 payload 做过滤——单 "Dataset" collection 思路，支持一次跨多知识库检索、生命周期简单。
点 id 直接用片段的 node_id(uuid 字符串)，payload 扁平存：
    {text, dataset_id, document_id, segment_id, document_enabled, segment_enabled}
启用/禁用 = 改 payload 标志位；删除 = 按 node_id 或按 dataset_id 过滤批删。

低层全部走原生 qdrant client（不套 LangChain QdrantVectorStore，避免其 page_content/metadata payload 键约束），
语义检索在 retrievers/semantic_retriever.py 里自己把 ScoredPoint 组装成 LCDocument。
"""
import os
from functools import lru_cache
from typing import Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchAny,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

# payload 字段名（与 indexing/retriever 共用，集中在此避免拼写漂移）
PAYLOAD_TEXT = "text"
PAYLOAD_DATASET_ID = "dataset_id"
PAYLOAD_DOCUMENT_ID = "document_id"
PAYLOAD_SEGMENT_ID = "segment_id"
PAYLOAD_DOCUMENT_ENABLED = "document_enabled"
PAYLOAD_SEGMENT_ENABLED = "segment_enabled"


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    host = os.getenv("QDRANT_HOST", "127.0.0.1")
    port = int(os.getenv("QDRANT_PORT", 6333))
    grpc_port = int(os.getenv("QDRANT_GRPC_PORT", 6334))
    api_key = os.getenv("QDRANT_API_KEY") or None
    prefer_grpc = (os.getenv("QDRANT_PREFER_GRPC", "False").lower() == "true")
    # 显式 https：qdrant-client 在设了 api_key 时会默认开 https，而内网 Qdrant 走纯 HTTP
    # （否则报 [SSL: WRONG_VERSION_NUMBER]）。默认 False，需要 TLS 时置 QDRANT_USE_HTTPS=true。
    https = (os.getenv("QDRANT_USE_HTTPS", "False").lower() == "true")
    return QdrantClient(
        host=host,
        port=port,
        grpc_port=grpc_port,
        prefer_grpc=prefer_grpc,
        api_key=api_key,
        https=https,
    )


def dataset_collection_name() -> str:
    return os.getenv("QDRANT_DATASET_COLLECTION", "ai_dataset")


# ---------------- collection 生命周期 ----------------

def ensure_collection(collection: str, vector_size: int, distance: Distance = Distance.COSINE) -> None:
    """通用：建不存在的 collection（仅向量配置）。"""
    client = get_qdrant_client()
    if not client.collection_exists(collection):
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=vector_size, distance=distance),
        )


def ensure_dataset_collection(vector_size: int) -> str:
    """确保知识库共享 collection 存在 + 建好过滤字段的 payload 索引。返回 collection 名。

    vector_size 由 EmbeddingsManager.vector_size 提供（当前 embedding 模型输出维）。
    """
    collection = dataset_collection_name()
    ensure_collection(collection, vector_size)
    client = get_qdrant_client()
    # 过滤字段建 payload 索引（重复创建是幂等的，异常忽略）
    for field, schema in (
        (PAYLOAD_DATASET_ID, PayloadSchemaType.INTEGER),
        (PAYLOAD_DOCUMENT_ID, PayloadSchemaType.INTEGER),
        (PAYLOAD_SEGMENT_ID, PayloadSchemaType.INTEGER),
        (PAYLOAD_DOCUMENT_ENABLED, PayloadSchemaType.BOOL),
        (PAYLOAD_SEGMENT_ENABLED, PayloadSchemaType.BOOL),
    ):
        try:
            client.create_payload_index(collection_name=collection, field_name=field, field_schema=schema)
        except Exception:
            pass
    return collection


# ---------------- 写入 / 更新 / 删除 ----------------

def build_payload(*, text: str, dataset_id: int, document_id: int, segment_id: int,
                  document_enabled: bool, segment_enabled: bool) -> dict:
    return {
        PAYLOAD_TEXT: text,
        PAYLOAD_DATASET_ID: int(dataset_id),
        PAYLOAD_DOCUMENT_ID: int(document_id),
        PAYLOAD_SEGMENT_ID: int(segment_id),
        PAYLOAD_DOCUMENT_ENABLED: bool(document_enabled),
        PAYLOAD_SEGMENT_ENABLED: bool(segment_enabled),
    }


def upsert_points(points: list, collection: Optional[str] = None) -> None:
    """points: list[PointStruct]（id=node_id, vector=向量, payload=build_payload(...)）。"""
    if not points:
        return
    client = get_qdrant_client()
    client.upsert(collection_name=collection or dataset_collection_name(), points=points)


def make_point(node_id: str, vector: list, payload: dict) -> PointStruct:
    return PointStruct(id=node_id, vector=vector, payload=payload)


def set_enabled(node_ids: list, *, document_enabled: Optional[bool] = None,
                segment_enabled: Optional[bool] = None, collection: Optional[str] = None) -> None:
    """改一批点的启用标志位（document/segment 任一或两者）。"""
    if not node_ids:
        return
    payload = {}
    if document_enabled is not None:
        payload[PAYLOAD_DOCUMENT_ENABLED] = bool(document_enabled)
    if segment_enabled is not None:
        payload[PAYLOAD_SEGMENT_ENABLED] = bool(segment_enabled)
    if not payload:
        return
    client = get_qdrant_client()
    client.set_payload(collection_name=collection or dataset_collection_name(), payload=payload, points=list(node_ids))


def delete_points(node_ids: list, collection: Optional[str] = None) -> None:
    if not node_ids:
        return
    client = get_qdrant_client()
    client.delete(collection_name=collection or dataset_collection_name(), points_selector=list(node_ids))


def delete_by_dataset(dataset_id: int, collection: Optional[str] = None) -> None:
    client = get_qdrant_client()
    flt = Filter(must=[FieldCondition(key=PAYLOAD_DATASET_ID, match=MatchValue(value=int(dataset_id)))])
    client.delete(collection_name=collection or dataset_collection_name(), points_selector=FilterSelector(filter=flt))


def delete_by_document(document_id: int, collection: Optional[str] = None) -> None:
    client = get_qdrant_client()
    flt = Filter(must=[FieldCondition(key=PAYLOAD_DOCUMENT_ID, match=MatchValue(value=int(document_id)))])
    client.delete(collection_name=collection or dataset_collection_name(), points_selector=FilterSelector(filter=flt))


# ---------------- 检索 ----------------

def build_enabled_filter(dataset_ids: list) -> Filter:
    """dataset_id ∈ dataset_ids 且 document_enabled、segment_enabled 均为 True。"""
    return Filter(must=[
        FieldCondition(key=PAYLOAD_DATASET_ID, match=MatchAny(any=[int(d) for d in dataset_ids])),
        FieldCondition(key=PAYLOAD_DOCUMENT_ENABLED, match=MatchValue(value=True)),
        FieldCondition(key=PAYLOAD_SEGMENT_ENABLED, match=MatchValue(value=True)),
    ])


def search(query_vector: list, dataset_ids: list, k: int = 4,
           score_threshold: float = 0.0, collection: Optional[str] = None) -> list:
    """语义检索：返回 list[ScoredPoint]（含 id / score / payload）。"""
    if not dataset_ids:
        return []
    client = get_qdrant_client()
    res = client.query_points(
        collection_name=collection or dataset_collection_name(),
        query=query_vector,
        limit=k,
        query_filter=build_enabled_filter(dataset_ids),
        score_threshold=(score_threshold or None),
        with_payload=True,
    )
    return list(getattr(res, "points", []) or [])


# ---------------- 兼容旧用法（保留，未在知识库链路使用）----------------

def get_vector_store(collection: str, embeddings: Any):
    """返回 LangChain QdrantVectorStore 实例。调用方自行保证 collection 已存在或先 ensure_collection。"""
    from langchain_qdrant import QdrantVectorStore
    client = get_qdrant_client()
    return QdrantVectorStore(client=client, collection_name=collection, embedding=embeddings)
