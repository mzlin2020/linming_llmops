"""语义检索器（向量相似度）。

LangChain BaseRetriever 子类——既能单独 invoke，也能塞进 EnsembleRetriever 做混合检索。
query 用 embeddings.embed_query 向量化（query 侧带指令前缀），经 vector_store.search 过滤
（dataset_id ∈ dataset_ids 且 document/segment 均 enabled），ScoredPoint → LCDocument，score 写入 metadata。
"""
from typing import Any, List

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document as LCDocument
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict

from internal.core.vector_store import qdrant_vector_store as vs


class SemanticRetriever(BaseRetriever):
    """相似性检索器 / 向量检索器。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    dataset_ids: List[int]
    embeddings: Any            # EmbeddingsManager.embeddings（LangChain Embeddings）
    k: int = 4
    score: float = 0.0

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun,
    ) -> List[LCDocument]:
        query_vector = self.embeddings.embed_query(query)
        points = vs.search(query_vector, self.dataset_ids, k=self.k, score_threshold=self.score)

        documents: List[LCDocument] = []
        for p in points:
            payload = p.payload or {}
            documents.append(LCDocument(
                page_content=payload.get(vs.PAYLOAD_TEXT, "") or "",
                metadata={
                    "dataset_id": payload.get(vs.PAYLOAD_DATASET_ID),
                    "document_id": payload.get(vs.PAYLOAD_DOCUMENT_ID),
                    "segment_id": payload.get(vs.PAYLOAD_SEGMENT_ID),
                    "node_id": str(p.id),
                    "score": float(p.score) if p.score is not None else 0.0,
                },
            ))
        return documents
