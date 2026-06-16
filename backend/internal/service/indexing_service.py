"""IndexingService：文档异步索引管线（Celery worker 内执行）+ 启停/删除时的向量库清理。

4 阶段（状态机写回 ai_document.status）：
  _parsing   FileExtractor 读文件 → 纯文本（clean_text 预处理）
  _splitting 切分 → 建 ai_segment 行（status=waiting，enabled=False）
  _indexing  jieba 抽关键词写回片段
  _completed 批量 embedding → Qdrant upsert（payload 标志位置 True）→ 片段/文档置 completed+enabled → 关键词倒排表入库
任一步异常 → 文档置 error 并记 error/stopped_at（不影响同批其它文档）。

清理：update_document_enabled / delete_document / delete_dataset 由 service 同步删行后，
本服务在 worker 里做向量库 + 关键词表的善后（按 document_id / dataset_id 过滤删向量）。
"""
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

from injector import inject

from internal.core.embeddings import EmbeddingsManager
from internal.core.file_extractor import file_extractor
from internal.core.vector_store import qdrant_vector_store as vs
from internal.entity import (
    DEFAULT_MAX_KEYWORD_PER_CHUNK,
    DEFAULT_PROCESS_RULE,
    DocumentStatus,
    SegmentStatus,
)
from internal.extension.database_extension import db
from internal.extension.redis_extension import redis_client
from internal.model import Document, ProcessRule, Segment, UploadFile
from internal.service.jieba_service import JiebaService
from internal.service.keyword_table_service import KeywordTableService
from internal.service.process_rule_service import ProcessRuleService
from internal.service.upload_file_service import UploadFileService
from internal.lib.helper import generate_text_hash as _hash

# embedding 单批大小：bge + torch 在低内存机上做推理时，批越大瞬时内存峰值越高，
# 故默认收到 8 削峰（env EMBED_BATCH 可调）。
_EMBED_BATCH = max(1, int(os.getenv("EMBED_BATCH", "8") or 8))

# 单文档构建重试上限：worker 被 OOM 杀死会触发 celery 自动重投(acks_late+reject_on_worker_lost)，
# 用 redis 计数兜底，超过上限直接标 error，避免「反复 OOM→反复重投」死循环。
_MAX_BUILD_ATTEMPTS = max(1, int(os.getenv("DOC_BUILD_MAX_ATTEMPTS", "3") or 3))
_BUILD_ATTEMPT_TTL = 2 * 60 * 60  # 计数键 2h 过期，正常完成会主动清除
_ATTEMPT_KEY = "ai:doc_build_attempt:{doc_id}"

# 卡死阈值：处于中间态(parsing/splitting/indexing)且开始时间早于此阈值的文档视为「索引中断」。
_STUCK_THRESHOLD_MIN = max(1, int(os.getenv("DOC_STUCK_THRESHOLD_MIN", "15") or 15))


@inject
@dataclass
class IndexingService:
    process_rule_service: ProcessRuleService
    jieba_service: JiebaService
    keyword_table_service: KeywordTableService
    upload_file_service: UploadFileService
    embeddings_manager: EmbeddingsManager

    # ---------------- 构建 ----------------

    def build_documents(self, document_ids: List[int]) -> None:
        documents = db.session.query(Document).filter(Document.id.in_(document_ids)).all()
        for document in documents:
            # 重试上限兜底：worker 被 OOM 杀死时任务会被 celery 重投，这里按文档累计尝试次数，
            # 超过上限直接标 error 并清计数，打破「OOM→重投→再 OOM」的死循环。
            attempts = self._bump_attempt(document.id)
            if attempts > _MAX_BUILD_ATTEMPTS:
                logging.error("文档索引超过最大重试次数 document_id=%s attempts=%s", document.id, attempts)
                self._mark_error(document, RuntimeError(
                    "索引多次中断（可能文档过大或服务内存不足），请重试或拆分文档后重新上传",
                ))
                self._clear_attempt(document.id)
                continue
            try:
                self._build_one(document)
                self._clear_attempt(document.id)  # 成功即清计数
            except Exception as e:  # 单文档受控失败不影响同批其它文档，也无需重投
                logging.exception("文档索引失败 document_id=%s", document.id)
                self._mark_error(document, e)
                self._clear_attempt(document.id)

    def _build_one(self, document: Document) -> None:
        # 幂等：清掉上一轮可能残留的片段/向量/关键词，保证重投或手动重索引不会产生重复数据。
        self._purge_partial(document)
        upload_file = db.session.get(UploadFile, document.upload_file_id) if document.upload_file_id else None
        process_rule = db.session.get(ProcessRule, document.process_rule_id) if document.process_rule_id else None
        rule = (process_rule.rule if process_rule else None) or DEFAULT_PROCESS_RULE["rule"]

        # 1. parsing
        with db.auto_commit():
            document.status = DocumentStatus.PARSING.value
            document.processing_started_at = datetime.utcnow()
        if upload_file is None:
            raise ValueError("文档缺少关联的上传文件")
        raw_text = file_extractor.load_text(self.upload_file_service.absolute_path(upload_file), upload_file.extension)
        text = self.process_rule_service.clean_text_by_rule(raw_text, rule)

        # 2. splitting
        with db.auto_commit():
            document.status = DocumentStatus.SPLITTING.value
            document.parsing_completed_at = datetime.utcnow()
        segments = self._split(document, text, rule)
        if not segments:
            raise ValueError("文档解析后没有可索引的内容")

        # 3. indexing（关键词）
        with db.auto_commit():
            document.status = DocumentStatus.INDEXING.value
            document.splitting_completed_at = datetime.utcnow()
        self._index_keywords(segments)

        # 4. completed（embedding + 向量库 + 关键词倒排表）
        self._complete(document, segments)

    def _split(self, document: Document, text: str, rule: dict) -> List[Segment]:
        splitter = self.process_rule_service.get_text_splitter_by_rule(
            rule, self.embeddings_manager.calculate_token_count,
        )
        chunks = [c for c in splitter.split_text(text) if c.strip()]
        segments: List[Segment] = []
        now = datetime.utcnow()
        for i, chunk in enumerate(chunks):
            seg = Segment(
                user_id=document.user_id,
                dataset_id=document.dataset_id,
                document_id=document.id,
                node_id=str(uuid.uuid4()),
                position=i + 1,
                content=chunk,
                character_count=len(chunk),
                token_count=self.embeddings_manager.calculate_token_count(chunk),
                keywords=[],
                hash=_hash(chunk),
                status=SegmentStatus.WAITING.value,
                enabled=False,
                processing_started_at=now,
            )
            db.session.add(seg)
            segments.append(seg)
        with db.auto_commit():
            document.character_count = len(text)
            document.token_count = sum(s.token_count for s in segments)
        for s in segments:  # 确保拿到自增 id
            db.session.refresh(s)
        return segments

    def _index_keywords(self, segments: List[Segment]) -> None:
        with db.auto_commit():
            for seg in segments:
                seg.keywords = self.jieba_service.extract_keywords(seg.content, DEFAULT_MAX_KEYWORD_PER_CHUNK)

    def _complete(self, document: Document, segments: List[Segment]) -> None:
        embeddings = self.embeddings_manager.embeddings
        collection = vs.ensure_dataset_collection(self.embeddings_manager.vector_size)

        for i in range(0, len(segments), _EMBED_BATCH):
            batch = segments[i:i + _EMBED_BATCH]
            vectors = embeddings.embed_documents([s.content for s in batch])
            points = [
                vs.make_point(
                    s.node_id, vec,
                    vs.build_payload(
                        text=s.content, dataset_id=document.dataset_id, document_id=document.id,
                        segment_id=s.id, document_enabled=True, segment_enabled=True,
                    ),
                )
                for s, vec in zip(batch, vectors)
            ]
            vs.upsert_points(points, collection)

        now = datetime.utcnow()
        with db.auto_commit():
            for s in segments:
                s.enabled = True
                s.status = SegmentStatus.COMPLETED.value
                s.indexing_completed_at = now
                s.completed_at = now
            document.enabled = True
            document.status = DocumentStatus.COMPLETED.value
            document.indexing_completed_at = now
            document.completed_at = now

        self.keyword_table_service.add_keyword_table_from_ids(
            document.dataset_id, [s.id for s in segments],
        )

    def _mark_error(self, document: Document, error: Exception) -> None:
        try:
            with db.auto_commit():
                document.status = DocumentStatus.ERROR.value
                document.error = str(error)[:500]
                document.stopped_at = datetime.utcnow()
        except Exception:
            db.session.rollback()

    def _purge_partial(self, document: Document) -> None:
        """重建前清掉该文档可能残留的片段行 / 向量 / 关键词倒排，使 build 幂等（重投、手动重索引均安全）。

        仅在确有残留片段时才清关键词/向量——首次构建无残留，可避免对尚未创建的 collection 误删 404。
        """
        seg_ids = [row[0] for row in db.session.query(Segment.id).filter(
            Segment.document_id == document.id,
        ).all()]
        if seg_ids:
            self.keyword_table_service.delete_keyword_table_from_ids(document.dataset_id, seg_ids)
            try:
                vs.delete_by_document(document.id)
            except Exception:  # collection 可能尚不存在/已删，不应阻断重建
                logging.warning("清理残留向量失败 document_id=%s", document.id, exc_info=True)
            with db.auto_commit():
                db.session.query(Segment).filter(Segment.document_id == document.id).delete()
        with db.auto_commit():
            document.character_count = 0
            document.token_count = 0
            document.enabled = False
            document.error = ""

    # ---------------- 卡死恢复（worker 启动钩子调用）----------------

    def recover_stuck_documents(self) -> int:
        """把卡在中间态(parsing/splitting/indexing)且超阈值无进展的文档复位为 error。

        覆盖「worker/容器被 OOM 杀死、在途任务丢失且未重投」留下的永久『索引中』残留——
        复位后前端即可看到失败并重新索引。返回复位的文档数。
        """
        cutoff = datetime.utcnow() - timedelta(minutes=_STUCK_THRESHOLD_MIN)
        transient = [
            DocumentStatus.PARSING.value,
            DocumentStatus.SPLITTING.value,
            DocumentStatus.INDEXING.value,
        ]
        stuck = db.session.query(Document).filter(
            Document.status.in_(transient),
            Document.processing_started_at.isnot(None),
            Document.processing_started_at < cutoff,
        ).all()
        for document in stuck:
            logging.warning("复位卡死文档 document_id=%s status=%s", document.id, document.status)
            self._mark_error(document, RuntimeError("索引中断（服务异常退出），请重新索引"))
            self._clear_attempt(document.id)
        return len(stuck)

    # ---------------- 构建重试计数（redis；不可用时降级为不限制）----------------

    @staticmethod
    def _bump_attempt(document_id: int) -> int:
        try:
            key = _ATTEMPT_KEY.format(doc_id=document_id)
            n = int(redis_client.incr(key))
            redis_client.expire(key, _BUILD_ATTEMPT_TTL)
            return n
        except Exception:  # redis 异常不应阻断索引
            return 1

    @staticmethod
    def _clear_attempt(document_id: int) -> None:
        try:
            redis_client.delete(_ATTEMPT_KEY.format(doc_id=document_id))
        except Exception:
            pass

    # ---------------- 启停 / 删除善后（worker 内）----------------

    def update_document_enabled(self, document_id: int, enabled: bool) -> None:
        document = db.session.get(Document, document_id)
        if document is None:
            return
        segments = db.session.query(Segment).filter(Segment.document_id == document_id).all()
        vs.set_enabled([s.node_id for s in segments if s.node_id], document_enabled=enabled)
        if enabled:
            self.keyword_table_service.add_keyword_table_from_ids(
                document.dataset_id, [s.id for s in segments if s.enabled],
            )
        else:
            self.keyword_table_service.delete_keyword_table_from_ids(
                document.dataset_id, [s.id for s in segments],
            )

    def delete_document(self, dataset_id: int, document_id: int, segment_ids: List[int]) -> None:
        """文档行已被 service 同步删除（FK 级联清片段行）；这里清向量 + 关键词倒排表。"""
        vs.delete_by_document(document_id)
        self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, segment_ids or [])

    def delete_dataset(self, dataset_id: int) -> None:
        """知识库行已被 service 同步删除（FK 级联清文档/片段行）；这里清向量 + 旁路表行。"""
        from internal.model import DatasetQuery, KeywordTable, ProcessRule as ProcessRuleModel

        vs.delete_by_dataset(dataset_id)
        with db.auto_commit():
            db.session.query(KeywordTable).filter(KeywordTable.dataset_id == dataset_id).delete()
            db.session.query(DatasetQuery).filter(DatasetQuery.dataset_id == dataset_id).delete()
            db.session.query(ProcessRuleModel).filter(ProcessRuleModel.dataset_id == dataset_id).delete()
