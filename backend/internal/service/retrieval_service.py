"""RetrievalService：知识库检索（命中测试 + 预留的 agent 检索工具）。

search_in_datasets：校验知识库归属 → 按策略(semantic/full_text/hybrid)构检索器 → 检索 →
记录查询历史(ai_dataset_query) + 命中片段 hit_count+1 → 返回带 score 的 LangChain 文档列表。

create_langchain_tool_from_search：把检索包成一个 dataset_retrieval 工具，由 chat_service 在应用
绑定了知识库（app_config.datasets）时挂进 FunctionCallAgent。
"""
from dataclasses import dataclass
from typing import List, Optional

from injector import inject
from langchain_core.documents import Document as LCDocument
from sqlalchemy import update

from internal.core.embeddings import EmbeddingsManager
from internal.core.retrievers import FullTextRetriever, SemanticRetriever
from internal.entity import (
    DEFAULT_RETRIEVAL_K,
    DEFAULT_RETRIEVAL_SCORE,
    RetrievalSource,
    RetrievalStrategy,
)
from internal.exception import NotFoundException
from internal.extension.database_extension import db
from internal.model import Dataset, DatasetQuery, Segment

DATASET_RETRIEVAL_TOOL_NAME = "dataset_retrieval"


def _combine_documents(documents: List[LCDocument]) -> str:
    return "\n\n".join(d.page_content for d in documents if (d.page_content or "").strip())


def _import_ensemble_retriever():
    """EnsembleRetriever 在 langchain 1.x 迁到了 langchain_classic.retrievers；兼容多个路径。"""
    for path in ("langchain_classic.retrievers", "langchain.retrievers", "langchain_community.retrievers"):
        try:
            mod = __import__(path, fromlist=["EnsembleRetriever"])
            return getattr(mod, "EnsembleRetriever")
        except Exception:
            continue
    raise RuntimeError("EnsembleRetriever 不可用，请改用 semantic 或 full_text 检索策略")


@inject
@dataclass
class RetrievalService:
    embeddings_manager: EmbeddingsManager

    def search_in_datasets(
        self,
        dataset_ids: List[int],
        query: str,
        *,
        user_id: int,
        retrieval_strategy: str = RetrievalStrategy.SEMANTIC.value,
        k: int = DEFAULT_RETRIEVAL_K,
        score: float = DEFAULT_RETRIEVAL_SCORE,
        source: str = RetrievalSource.HIT_TESTING.value,
        source_app_id: Optional[int] = None,
    ) -> List[LCDocument]:
        # 1. 校验知识库归属（只检索属于该 user 的库）
        datasets = db.session.query(Dataset).filter(
            Dataset.id.in_(dataset_ids), Dataset.user_id == user_id,
        ).all()
        if not datasets:
            raise NotFoundException(message="当前无知识库可执行检索")
        owned_ids = [d.id for d in datasets]

        # 2. 按策略检索
        semantic = SemanticRetriever(
            dataset_ids=owned_ids, embeddings=self.embeddings_manager.embeddings, k=k, score=score,
        )
        full_text = FullTextRetriever(dataset_ids=owned_ids, k=k)
        if retrieval_strategy == RetrievalStrategy.FULL_TEXT.value:
            documents = full_text.invoke(query)[:k]
        elif retrieval_strategy == RetrievalStrategy.HYBRID.value:
            EnsembleRetriever = _import_ensemble_retriever()
            hybrid = EnsembleRetriever(retrievers=[semantic, full_text], weights=[0.5, 0.5])
            documents = hybrid.invoke(query)[:k]
        else:
            documents = semantic.invoke(query)[:k]

        # 3. 记录查询历史（一个知识库一条）+ 命中片段 hit_count+1
        unique_dataset_ids = {d.metadata.get("dataset_id") for d in documents if d.metadata.get("dataset_id")}
        segment_ids = [d.metadata.get("segment_id") for d in documents if d.metadata.get("segment_id")]
        with db.auto_commit():
            for ds_id in unique_dataset_ids:
                db.session.add(DatasetQuery(
                    dataset_id=ds_id, query=query, source=source,
                    source_app_id=source_app_id, created_by=user_id,
                ))
            if segment_ids:
                db.session.execute(
                    update(Segment).where(Segment.id.in_(segment_ids)).values(hit_count=Segment.hit_count + 1)
                )
        return documents

    def create_langchain_tool_from_search(
        self,
        dataset_ids: List[int],
        user_id: int,
        *,
        retrieval_strategy: str = RetrievalStrategy.SEMANTIC.value,
        k: int = DEFAULT_RETRIEVAL_K,
        score: float = DEFAULT_RETRIEVAL_SCORE,
        source: str = RetrievalSource.APP.value,
        source_app_id: Optional[int] = None,
    ):
        """构建 dataset_retrieval 工具（由 chat_service 按 app_config.datasets 挂进 FunctionCallAgent）。"""
        from langchain_core.tools import tool
        from pydantic import BaseModel, Field

        class DatasetRetrievalInput(BaseModel):
            query: str = Field(description="知识库检索 query 语句")

        service = self

        @tool(DATASET_RETRIEVAL_TOOL_NAME, args_schema=DatasetRetrievalInput)
        def dataset_retrieval(query: str) -> str:
            """当用户的问题可能涉及专属/扩展知识时，调用本工具检索知识库，输入检索 query，返回相关内容文本。"""
            documents = service.search_in_datasets(
                dataset_ids, query, user_id=user_id,
                retrieval_strategy=retrieval_strategy, k=k, score=score,
                source=source, source_app_id=source_app_id,
            )
            return _combine_documents(documents) or "知识库内没有检索到对应内容"

        return dataset_retrieval
