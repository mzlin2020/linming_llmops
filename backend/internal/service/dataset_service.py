"""DatasetService：知识库 CRUD + 命中测试 + 查询历史（按 user_id 归属）。

模块级 db、手动分页、越权抛 NotFoundException。
删除：同步删 ai_dataset 行（FK 级联清文档/片段行）后，派发 delete_dataset 异步任务清向量库与旁路表。
命中测试：委托 RetrievalService 检索，再回表把片段详情组装成响应。
"""
from dataclasses import dataclass
from typing import Optional

from injector import inject
from sqlalchemy import desc

from internal.entity import DEFAULT_RETRIEVAL_K, DEFAULT_RETRIEVAL_SCORE, RetrievalStrategy
from internal.exception import NotFoundException, ValidateErrorException
from internal.extension.database_extension import db
from internal.model import Account, Dataset, DatasetQuery, Document, Segment
from internal.service.quota_service import QuotaService
from internal.service.retrieval_service import RetrievalService
from pkg.paginator import Paginator


def _dataset_dict(ds: Dataset) -> dict:
    return {
        "id": ds.id,
        "name": ds.name,
        "icon": ds.icon,
        "description": ds.description,
        "document_count": ds.document_count,
        "character_count": ds.character_count,
        "hit_count": ds.hit_count,
        "created_at": int(ds.created_at.timestamp()) if ds.created_at else 0,
        "updated_at": int(ds.updated_at.timestamp()) if ds.updated_at else 0,
    }


@inject
@dataclass
class DatasetService:
    retrieval_service: RetrievalService
    quota_service: QuotaService

    # ---------- CRUD ----------

    def create_dataset(self, name: str, icon: str, description: str, user: Account) -> Dataset:
        self.quota_service.check_create_dataset(user)
        self._ensure_name_available(name, user.id)
        ds = Dataset(user_id=user.id, name=name, icon=icon or "", description=description or "")
        with db.auto_commit():
            db.session.add(ds)
        db.session.refresh(ds)
        return ds

    def update_dataset(self, dataset_id: int, name: str, icon: str, description: str, user: Account) -> Dataset:
        ds = self._get_owned(dataset_id, user.id)
        self._ensure_name_available(name, user.id, exclude_id=ds.id)
        with db.auto_commit():
            ds.name = name
            ds.icon = icon or ""
            ds.description = description or ""
        return ds

    def get_dataset(self, dataset_id: int, user: Account) -> dict:
        return _dataset_dict(self._get_owned(dataset_id, user.id))

    def get_datasets_with_page(self, current_page: int, page_size: int, search_word: Optional[str], user: Account) -> dict:
        query = db.session.query(Dataset).filter(Dataset.user_id == user.id)
        if search_word:
            query = query.filter(Dataset.name.like(f"%{search_word}%"))
        paginator = Paginator(page=current_page, page_size=page_size, total_record=query.count())
        rows = (
            query.order_by(desc(Dataset.created_at))
            .offset(paginator.offset)
            .limit(page_size)
            .all()
        )
        paginator.items = [_dataset_dict(d) for d in rows]
        return paginator.to_dict()

    def delete_dataset(self, dataset_id: int, user: Account) -> None:
        ds = self._get_owned(dataset_id, user.id)
        from internal.task.dataset_task import delete_dataset as delete_dataset_task
        with db.auto_commit():
            db.session.delete(ds)  # FK 级联清 ai_document / ai_segment
        delete_dataset_task.delay(dataset_id)  # 异步清向量库 + ai_keyword_table/ai_dataset_query/ai_process_rule

    # ---------- 命中测试 ----------

    def hit(self, dataset_id: int, query: str, user: Account,
            retrieval_strategy: str = RetrievalStrategy.SEMANTIC.value,
            k: int = DEFAULT_RETRIEVAL_K, score: float = DEFAULT_RETRIEVAL_SCORE) -> list:
        self._get_owned(dataset_id, user.id)
        self.quota_service.check_hit(user)
        documents = self.retrieval_service.search_in_datasets(
            [dataset_id], query, user_id=user.id,
            retrieval_strategy=retrieval_strategy, k=k, score=score,
        )
        if not documents:
            return []

        # 回表补片段/文档详情
        segment_ids = [d.metadata.get("segment_id") for d in documents if d.metadata.get("segment_id")]
        segments = {s.id: s for s in db.session.query(Segment).filter(Segment.id.in_(segment_ids)).all()}
        doc_ids = {s.document_id for s in segments.values()}
        docs = {d.id: d for d in db.session.query(Document).filter(Document.id.in_(doc_ids)).all()}

        results = []
        for d in documents:
            seg = segments.get(d.metadata.get("segment_id"))
            if seg is None:
                continue
            document = docs.get(seg.document_id)
            results.append({
                "id": seg.id,
                "document": {"id": document.id, "name": document.name} if document else None,
                "dataset_id": seg.dataset_id,
                "score": d.metadata.get("score", 0.0),
                "position": seg.position,
                "content": seg.content,
                "keywords": seg.keywords or [],
                "character_count": seg.character_count,
                "token_count": seg.token_count,
                "hit_count": seg.hit_count,
                "enabled": seg.enabled,
            })
        return results

    def get_dataset_queries(self, dataset_id: int, user: Account, limit: int = 10) -> list:
        self._get_owned(dataset_id, user.id)
        rows = (
            db.session.query(DatasetQuery)
            .filter(DatasetQuery.dataset_id == dataset_id)
            .order_by(desc(DatasetQuery.created_at))
            .limit(limit)
            .all()
        )
        return [
            {
                "id": q.id,
                "query": q.query,
                "source": q.source,
                "created_at": int(q.created_at.timestamp()) if q.created_at else 0,
            }
            for q in rows
        ]

    # ---------- internal ----------

    def _get_owned(self, dataset_id: int, user_id: int) -> Dataset:
        ds = db.session.get(Dataset, dataset_id)
        if ds is None or ds.user_id != user_id:
            raise NotFoundException(message="该知识库不存在")
        return ds

    def _ensure_name_available(self, name: str, user_id: int, exclude_id: Optional[int] = None) -> None:
        query = db.session.query(Dataset).filter(Dataset.user_id == user_id, Dataset.name == name)
        if exclude_id is not None:
            query = query.filter(Dataset.id != exclude_id)
        if query.first():
            raise ValidateErrorException(message=f"知识库名 {name} 已存在")
