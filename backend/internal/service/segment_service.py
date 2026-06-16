"""SegmentService：片段的查/增/改/启停/删（控制台手动维护）。

与文档索引的异步管线不同，片段的手动操作是**同步**的：增删改即时更新 Qdrant（payload 标志/向量）
与关键词倒排表，保证命中测试立刻可见。所有操作按 user_id 归属校验，越权一律 404（不泄露存在性）。
"""
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from injector import inject

from internal.core.embeddings import EmbeddingsManager
from internal.core.vector_store import qdrant_vector_store as vs
from internal.entity import DEFAULT_MAX_KEYWORD_PER_CHUNK, DocumentStatus, SegmentStatus
from internal.exception import ForbiddenException, NotFoundException, ValidateErrorException
from internal.extension.database_extension import db
from internal.model import Account, Document, Segment
from internal.schema.conversation_schema import PaginatorReq
from internal.service.jieba_service import JiebaService
from internal.service.keyword_table_service import KeywordTableService
from internal.lib.helper import generate_text_hash as _hash
from pkg.paginator import Paginator

_MAX_SEGMENT_TOKEN = 1000


def _segment_dict(seg: Segment) -> dict:
    return {
        "id": seg.id,
        "document_id": seg.document_id,
        "dataset_id": seg.dataset_id,
        "position": seg.position,
        "content": seg.content,
        "keywords": seg.keywords or [],
        "character_count": seg.character_count,
        "token_count": seg.token_count,
        "hit_count": seg.hit_count,
        "enabled": seg.enabled,
        "status": seg.status,
        "error": seg.error,
        "created_at": int(seg.created_at.timestamp()) if seg.created_at else 0,
    }


@inject
@dataclass
class SegmentService:
    embeddings_manager: EmbeddingsManager
    keyword_table_service: KeywordTableService
    jieba_service: JiebaService

    # ---------- 查询 ----------

    def get_segments_with_page(self, user: Account, dataset_id: int, document_id: int, req: PaginatorReq) -> dict:
        document = self._get_owned_document(user, dataset_id, document_id)
        query = db.session.query(Segment).filter(Segment.document_id == document.id)
        paginator = Paginator(page=req.current_page, page_size=req.page_size, total_record=query.count())
        rows = (
            query.order_by(Segment.position.asc())
            .offset(paginator.offset)
            .limit(req.page_size)
            .all()
        )
        paginator.items = [_segment_dict(s) for s in rows]
        return paginator.to_dict()

    def get_segment(self, user: Account, dataset_id: int, document_id: int, segment_id: int) -> dict:
        return _segment_dict(self._get_owned_segment(user, dataset_id, document_id, segment_id))

    # ---------- 增 / 改 ----------

    def create_segment(self, user: Account, dataset_id: int, document_id: int, content: str, keywords=None) -> dict:
        document = self._get_owned_document(user, dataset_id, document_id)
        if document.status != DocumentStatus.COMPLETED.value:
            raise ValidateErrorException(message="文档尚未索引完成，无法新增片段")
        content = (content or "").strip()
        if not content:
            raise ValidateErrorException(message="片段内容不能为空")
        token_count = self.embeddings_manager.calculate_token_count(content)
        if token_count > _MAX_SEGMENT_TOKEN:
            raise ValidateErrorException(message=f"片段内容过长（token 数 {token_count} 超过 {_MAX_SEGMENT_TOKEN}）")

        keywords = keywords or self.jieba_service.extract_keywords(content, DEFAULT_MAX_KEYWORD_PER_CHUNK)
        max_position = db.session.query(db.func.max(Segment.position)).filter(
            Segment.document_id == document.id
        ).scalar() or 0
        now = datetime.utcnow()
        seg = Segment(
            user_id=user.id, dataset_id=dataset_id, document_id=document.id,
            node_id=str(uuid.uuid4()), position=max_position + 1, content=content,
            character_count=len(content), token_count=token_count, keywords=keywords,
            hash=_hash(content), enabled=True, status=SegmentStatus.COMPLETED.value,
            processing_started_at=now, indexing_completed_at=now, completed_at=now,
        )
        with db.auto_commit():
            db.session.add(seg)
        db.session.refresh(seg)

        # 同步写向量库 + 关键词倒排表
        collection = vs.ensure_dataset_collection(self.embeddings_manager.vector_size)
        vector = self.embeddings_manager.embeddings.embed_documents([content])[0]
        vs.upsert_points([vs.make_point(seg.node_id, vector, vs.build_payload(
            text=content, dataset_id=dataset_id, document_id=document.id, segment_id=seg.id,
            document_enabled=document.enabled, segment_enabled=True,
        ))], collection)
        self.keyword_table_service.add_keyword_table_from_ids(dataset_id, [seg.id])
        self._recount_document(document)
        return _segment_dict(seg)

    def update_segment(self, user: Account, dataset_id: int, document_id: int, segment_id: int,
                       content: str, keywords=None) -> dict:
        seg = self._get_owned_segment(user, dataset_id, document_id, segment_id)
        if seg.status != SegmentStatus.COMPLETED.value:
            raise ValidateErrorException(message="片段尚未就绪，无法编辑")
        content = (content or "").strip()
        if not content:
            raise ValidateErrorException(message="片段内容不能为空")
        token_count = self.embeddings_manager.calculate_token_count(content)
        if token_count > _MAX_SEGMENT_TOKEN:
            raise ValidateErrorException(message=f"片段内容过长（token 数 {token_count} 超过 {_MAX_SEGMENT_TOKEN}）")

        content_changed = _hash(content) != seg.hash
        new_keywords = keywords or self.jieba_service.extract_keywords(content, DEFAULT_MAX_KEYWORD_PER_CHUNK)

        # 关键词倒排表：先删旧、再加新
        self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, [seg.id])
        with db.auto_commit():
            seg.content = content
            seg.character_count = len(content)
            seg.token_count = token_count
            seg.keywords = new_keywords
            seg.hash = _hash(content)
        if seg.enabled:
            self.keyword_table_service.add_keyword_table_from_ids(dataset_id, [seg.id])

        # 向量库：内容变了重算向量，否则只改文本 payload
        collection = vs.ensure_dataset_collection(self.embeddings_manager.vector_size)
        document = db.session.get(Document, document_id)
        if content_changed:
            vector = self.embeddings_manager.embeddings.embed_documents([content])[0]
            vs.upsert_points([vs.make_point(seg.node_id, vector, vs.build_payload(
                text=content, dataset_id=dataset_id, document_id=document_id, segment_id=seg.id,
                document_enabled=document.enabled if document else True, segment_enabled=seg.enabled,
            ))], collection)
        self._recount_document(document)
        return _segment_dict(seg)

    # ---------- 启停 / 删 ----------

    def update_segment_enabled(self, user: Account, dataset_id: int, document_id: int,
                               segment_id: int, enabled: bool) -> None:
        seg = self._get_owned_segment(user, dataset_id, document_id, segment_id)
        if seg.status != SegmentStatus.COMPLETED.value:
            raise ValidateErrorException(message="片段尚未就绪，无法启停")
        with db.auto_commit():
            seg.enabled = enabled
            seg.disabled_at = None if enabled else datetime.utcnow()
        vs.set_enabled([seg.node_id], segment_enabled=enabled)
        if enabled:
            self.keyword_table_service.add_keyword_table_from_ids(dataset_id, [seg.id])
        else:
            self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, [seg.id])

    def delete_segment(self, user: Account, dataset_id: int, document_id: int, segment_id: int) -> None:
        seg = self._get_owned_segment(user, dataset_id, document_id, segment_id)
        node_id = seg.node_id
        document = db.session.get(Document, document_id)
        self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, [seg.id])
        with db.auto_commit():
            db.session.delete(seg)
        vs.delete_points([node_id])
        self._recount_document(document)

    # ---------- internal ----------

    def _recount_document(self, document: Optional[Document]) -> None:
        if document is None:
            return
        agg = db.session.query(
            db.func.coalesce(db.func.sum(Segment.character_count), 0),
            db.func.coalesce(db.func.sum(Segment.token_count), 0),
        ).filter(Segment.document_id == document.id).one()
        with db.auto_commit():
            document.character_count = int(agg[0] or 0)
            document.token_count = int(agg[1] or 0)

    def _get_owned_document(self, user: Account, dataset_id: int, document_id: int) -> Document:
        document = db.session.get(Document, document_id)
        if document is None or document.user_id != user.id or document.dataset_id != dataset_id:
            raise NotFoundException(message="该文档不存在")
        return document

    def _get_owned_segment(self, user: Account, dataset_id: int, document_id: int, segment_id: int) -> Segment:
        seg = db.session.get(Segment, segment_id)
        if seg is None or seg.user_id != user.id:
            raise NotFoundException(message="该片段不存在")
        if seg.document_id != document_id or seg.dataset_id != dataset_id:
            raise ForbiddenException(message="片段与文档/知识库不匹配")
        return seg
