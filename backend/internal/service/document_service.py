"""DocumentService：文档 CRUD + 批量上传建文档（触发异步索引）+ 批次状态轮询（按 user_id 归属）。

create_documents：校验知识库归属 + 上传文件归属/格式 → 建一份 ai_process_rule（整批共享）→ 逐个建
ai_document(status=waiting) → 派发 build_documents 异步任务 → 返回 {documents, batch}。
enable/disable、delete 都是"同步改 DB 行 + 派发异步任务善后向量库/关键词表"。
"""
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from injector import inject

from internal.core.file_extractor import is_supported
from internal.entity import DEFAULT_PROCESS_RULE, DocumentStatus, ProcessType
from internal.exception import NotFoundException, ValidateErrorException
from internal.extension.database_extension import db
from internal.model import Account, Dataset, Document, ProcessRule, Segment
from internal.service.quota_service import QuotaService
from internal.service.upload_file_service import UploadFileService
from pkg.paginator import Paginator


def _document_dict(doc: Document) -> dict:
    return {
        "id": doc.id,
        "dataset_id": doc.dataset_id,
        "name": doc.name,
        "position": doc.position,
        "character_count": doc.character_count,
        "token_count": doc.token_count,
        "segment_count": doc.segment_count,
        "hit_count": doc.hit_count,
        "enabled": doc.enabled,
        "status": doc.status,
        "error": doc.error,
        "batch": doc.batch,
        "created_at": int(doc.created_at.timestamp()) if doc.created_at else 0,
    }


@inject
@dataclass
class DocumentService:
    upload_file_service: UploadFileService
    quota_service: QuotaService

    # ---------- 批量上传建文档 ----------

    def create_documents(self, dataset_id: int, upload_file_ids: List[int], user: Account,
                         process_type: str = ProcessType.AUTOMATIC.value, rule: Optional[dict] = None) -> dict:
        dataset = self._get_owned_dataset(dataset_id, user.id)

        # 校验上传文件：归属 + 支持的格式
        valid_files = []
        for fid in upload_file_ids or []:
            uf = self.upload_file_service.get_owned(fid, user.id)
            if uf is not None and is_supported(uf.extension):
                valid_files.append(uf)
        if not valid_files:
            raise ValidateErrorException(message="没有有效的上传文件（不存在或格式不支持）")

        # 配额/限流：单库文档数上限 + 灌库预算（冷却 + 日次数）。对所有登录用户统一生效。
        self.quota_service.check_add_documents(user, dataset.id, len(valid_files))

        # 处理规则：automatic 用默认，custom 用传入 rule
        if process_type == ProcessType.CUSTOM.value and rule:
            rule_payload = rule
        else:
            rule_payload = DEFAULT_PROCESS_RULE["rule"]
        process_rule = ProcessRule(
            user_id=user.id, dataset_id=dataset.id,
            mode=process_type, rule=rule_payload,
        )
        with db.auto_commit():
            db.session.add(process_rule)
        db.session.refresh(process_rule)

        batch = datetime.utcnow().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:6]
        base_position = db.session.query(db.func.max(Document.position)).filter(
            Document.dataset_id == dataset.id
        ).scalar() or 0

        documents = []
        with db.auto_commit():
            for i, uf in enumerate(valid_files):
                doc = Document(
                    user_id=user.id, dataset_id=dataset.id,
                    upload_file_id=uf.id, process_rule_id=process_rule.id,
                    batch=batch, name=uf.name, position=base_position + i + 1,
                    status=DocumentStatus.WAITING.value, enabled=False,
                )
                db.session.add(doc)
                documents.append(doc)
        for doc in documents:
            db.session.refresh(doc)

        # 派发异步索引
        from internal.task.document_task import build_documents
        build_documents.delay([d.id for d in documents])
        self.quota_service.record_build(user)  # 记一次灌库（计冷却 + 日次数）

        return {"documents": [_document_dict(d) for d in documents], "batch": batch}

    # ---------- 查询 ----------

    def get_documents_with_page(self, dataset_id: int, current_page: int, page_size: int,
                                search_word: Optional[str], user: Account) -> dict:
        self._get_owned_dataset(dataset_id, user.id)
        query = db.session.query(Document).filter(Document.dataset_id == dataset_id)
        if search_word:
            query = query.filter(Document.name.like(f"%{search_word}%"))
        paginator = Paginator(page=current_page, page_size=page_size, total_record=query.count())
        rows = (
            query.order_by(Document.position.asc())
            .offset(paginator.offset)
            .limit(page_size)
            .all()
        )
        paginator.items = [_document_dict(d) for d in rows]
        return paginator.to_dict()

    def get_document(self, dataset_id: int, document_id: int, user: Account) -> dict:
        return _document_dict(self._get_owned_document(dataset_id, document_id, user.id))

    def get_documents_status(self, dataset_id: int, batch: str, user: Account) -> list:
        self._get_owned_dataset(dataset_id, user.id)
        rows = db.session.query(Document).filter(
            Document.dataset_id == dataset_id, Document.batch == batch,
        ).order_by(Document.position.asc()).all()
        result = []
        for doc in rows:
            seg_count = doc.segment_count
            completed = db.session.query(db.func.count(Segment.id)).filter(
                Segment.document_id == doc.id, Segment.status == "completed",
            ).scalar() or 0
            result.append({
                "id": doc.id,
                "name": doc.name,
                "status": doc.status,
                "error": doc.error,
                "segment_count": seg_count,
                "completed_segment_count": int(completed),
                "character_count": doc.character_count,
                "position": doc.position,
            })
        return result

    # ---------- 改名 / 启停 / 删 ----------

    def update_document_name(self, dataset_id: int, document_id: int, name: str, user: Account) -> dict:
        doc = self._get_owned_document(dataset_id, document_id, user.id)
        if not (name or "").strip():
            raise ValidateErrorException(message="文档名不能为空")
        with db.auto_commit():
            doc.name = name.strip()
        return _document_dict(doc)

    def update_document_enabled(self, dataset_id: int, document_id: int, enabled: bool, user: Account) -> None:
        doc = self._get_owned_document(dataset_id, document_id, user.id)
        if doc.status != DocumentStatus.COMPLETED.value:
            raise ValidateErrorException(message="文档尚未索引完成，无法启停")
        if doc.enabled == enabled:
            raise ValidateErrorException(message="文档状态未发生变化")
        with db.auto_commit():
            doc.enabled = enabled
            doc.disabled_at = None if enabled else datetime.utcnow()
        from internal.task.document_task import update_document_enabled as update_enabled_task
        update_enabled_task.delay(document_id, enabled)

    def reindex_document(self, dataset_id: int, document_id: int, user: Account) -> dict:
        """重新索引：仅允许终态(error/completed)文档复位为 waiting 并重新派发异步索引。

        build 已幂等（会先清掉残留片段/向量/关键词），故重投不会产生重复数据。
        """
        doc = self._get_owned_document(dataset_id, document_id, user.id)
        if doc.status not in (DocumentStatus.COMPLETED.value, DocumentStatus.ERROR.value):
            raise ValidateErrorException(message="文档正在处理中，暂时无法重新索引")
        # 配额/限流：重索引与灌库共用预算（冷却 + 日次数）。对所有登录用户统一生效。
        self.quota_service.check_reindex(user)
        with db.auto_commit():
            doc.status = DocumentStatus.WAITING.value
            doc.error = ""
            doc.enabled = False
            doc.stopped_at = None
        from internal.task.document_task import build_documents
        build_documents.delay([doc.id])
        self.quota_service.record_build(user)  # 记一次灌库（计冷却 + 日次数）
        return _document_dict(doc)

    def delete_document(self, dataset_id: int, document_id: int, user: Account) -> None:
        doc = self._get_owned_document(dataset_id, document_id, user.id)
        if doc.status not in (DocumentStatus.COMPLETED.value, DocumentStatus.ERROR.value):
            raise ValidateErrorException(message="文档正在处理中，暂时无法删除")
        segment_ids = [row[0] for row in db.session.query(Segment.id).filter(Segment.document_id == document_id).all()]
        with db.auto_commit():
            db.session.delete(doc)  # FK 级联清 ai_segment 行
        from internal.task.document_task import delete_document as delete_document_task
        delete_document_task.delay(dataset_id, document_id, segment_ids)

    # ---------- internal ----------

    def _get_owned_dataset(self, dataset_id: int, user_id: int) -> Dataset:
        ds = db.session.get(Dataset, dataset_id)
        if ds is None or ds.user_id != user_id:
            raise NotFoundException(message="该知识库不存在")
        return ds

    def _get_owned_document(self, dataset_id: int, document_id: int, user_id: int) -> Document:
        doc = db.session.get(Document, document_id)
        if doc is None or doc.user_id != user_id or doc.dataset_id != dataset_id:
            raise NotFoundException(message="该文档不存在")
        return doc
