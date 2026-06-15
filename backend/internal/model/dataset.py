"""自有表：知识库（RAG）相关 6 张表。全部 ai_ 前缀。

- ai_dataset        —— 知识库（一个用户可建多个）。统计量(document_count/character_count/hit_count)现算成 @property，不落列。
- ai_document       —— 知识库里的一份文档（一个上传文件 = 一份文档）。带异步索引状态机 + 各阶段时间戳。
- ai_segment        —— 文档切分后的片段（= 向量库一个点）。node_id 是 Qdrant point id。
- ai_keyword_table  —— 一个知识库一张关键词倒排表 {keyword: [segment_id...]}，供全文检索。
- ai_dataset_query  —— 知识库查询历史（命中测试 / 应用调用）。
- ai_process_rule   —— 文档切分规则（automatic/custom）。

级联：dataset →(FK CASCADE) document →(FK CASCADE) segment，删 dataset 行时 DB 自动清子表行；
keyword_table / dataset_query / process_rule 用普通 dataset_id 关联（不 FK），由 delete_dataset 异步任务清理，
同时异步任务按 dataset_id 过滤删除 Qdrant 中的向量点。
user_id 是普通索引列（= account.id），不加 FK。
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import relationship

from internal.extension.database_extension import db


class Dataset(db.Model):
    """知识库。"""

    __tablename__ = "ai_dataset"
    __table_args__ = (
        Index("ix_ai_dataset_user_id", "user_id"),
        Index("ix_ai_dataset_user_id_name", "user_id", "name"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, nullable=False, comment="归属账号 id（= account.id）",
    )
    name = Column(String(128), nullable=False, default="", server_default="", comment="知识库名（同用户内唯一）")
    icon = Column(String(512), nullable=False, default="", server_default="", comment="图标 URL")
    description = Column(Text, nullable=False, default="", server_default="", comment="知识库描述")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents = relationship(
        "Document", backref="dataset",
        cascade="all, delete-orphan", passive_deletes=True,
    )

    # ---------- 统计量：现算（知识库数量少，N+1 可接受；@property 风格）----------
    # 注意 func.sum 在 MySQL 返回 Decimal，Flask 会把 Decimal 序列化成字符串，故统一 int() 收口。
    @property
    def document_count(self) -> int:
        return int(db.session.query(func.count(Document.id)).filter(Document.dataset_id == self.id).scalar() or 0)

    @property
    def character_count(self) -> int:
        return int(db.session.query(func.coalesce(func.sum(Document.character_count), 0)).filter(
            Document.dataset_id == self.id
        ).scalar() or 0)

    @property
    def hit_count(self) -> int:
        return int(db.session.query(func.coalesce(func.sum(Segment.hit_count), 0)).filter(
            Segment.dataset_id == self.id
        ).scalar() or 0)


class Document(db.Model):
    """知识库里的一份文档（异步索引）。"""

    __tablename__ = "ai_document"
    __table_args__ = (
        Index("ix_ai_document_dataset_id", "dataset_id"),
        Index("ix_ai_document_dataset_id_batch", "dataset_id", "batch"),
        Index("ix_ai_document_user_id", "user_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, nullable=False, comment="归属账号 id（= account.id）",
    )
    dataset_id = Column(
        Integer,
        ForeignKey("ai_dataset.id", ondelete="CASCADE", name="fk_ai_document_dataset"),
        nullable=False, comment="所属知识库",
    )
    upload_file_id = Column(Integer, nullable=True, comment="对应 ai_upload_file.id（普通引用，不 FK）")
    process_rule_id = Column(Integer, nullable=True, comment="对应 ai_process_rule.id（普通引用，不 FK）")

    batch = Column(String(32), nullable=False, default="", server_default="", comment="处理批次（一次上传共享，供状态轮询）")
    name = Column(String(512), nullable=False, default="", server_default="", comment="文档名")
    position = Column(Integer, nullable=False, default=1, server_default="1", comment="文档在知识库内的位序")

    character_count = Column(Integer, nullable=False, default=0, server_default="0", comment="字符数")
    token_count = Column(Integer, nullable=False, default=0, server_default="0", comment="token 数")

    # 各阶段时间戳（异步索引流程进度）
    processing_started_at = Column(DateTime, nullable=True, comment="开始处理时间")
    parsing_completed_at = Column(DateTime, nullable=True, comment="解析完成时间")
    splitting_completed_at = Column(DateTime, nullable=True, comment="分割完成时间")
    indexing_completed_at = Column(DateTime, nullable=True, comment="索引完成时间")
    completed_at = Column(DateTime, nullable=True, comment="全部完成时间")
    stopped_at = Column(DateTime, nullable=True, comment="停止/出错时间")

    error = Column(Text, nullable=False, default="", server_default="", comment="错误信息")
    enabled = Column(Boolean, nullable=False, default=False, server_default=text("0"), comment="是否启用（命中检索）")
    disabled_at = Column(DateTime, nullable=True, comment="禁用时间")
    status = Column(
        String(32), nullable=False, default="waiting", server_default="waiting",
        comment="对齐 DocumentStatus: waiting/parsing/splitting/indexing/completed/error",
    )

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    segments = relationship(
        "Segment", backref="document",
        cascade="all, delete-orphan", passive_deletes=True,
    )

    @property
    def segment_count(self) -> int:
        return int(db.session.query(func.count(Segment.id)).filter(Segment.document_id == self.id).scalar() or 0)

    @property
    def hit_count(self) -> int:
        return int(db.session.query(func.coalesce(func.sum(Segment.hit_count), 0)).filter(
            Segment.document_id == self.id
        ).scalar() or 0)


class Segment(db.Model):
    """文档切分后的片段（= Qdrant 一个向量点）。"""

    __tablename__ = "ai_segment"
    __table_args__ = (
        Index("ix_ai_segment_document_id", "document_id"),
        Index("ix_ai_segment_dataset_id", "dataset_id"),
        Index("ix_ai_segment_node_id", "node_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, nullable=False, comment="归属账号 id（= account.id）",
    )
    dataset_id = Column(Integer, nullable=False, comment="所属知识库（冗余，便于全文检索/清理，不 FK）")
    document_id = Column(
        Integer,
        ForeignKey("ai_document.id", ondelete="CASCADE", name="fk_ai_segment_document"),
        nullable=False, comment="所属文档",
    )
    node_id = Column(String(64), nullable=False, default="", server_default="", comment="Qdrant 向量点 id（uuid）")

    position = Column(Integer, nullable=False, default=1, server_default="1", comment="片段在文档内的位序")
    content = Column(Text, nullable=False, default="", server_default="", comment="片段内容")
    character_count = Column(Integer, nullable=False, default=0, server_default="0", comment="字符数")
    token_count = Column(Integer, nullable=False, default=0, server_default="0", comment="token 数")
    keywords = Column(JSON, nullable=False, default=list, server_default=text("('[]')"), comment="关键词列表")
    hash = Column(String(128), nullable=False, default="", server_default="", comment="内容哈希（判断是否需重建向量）")
    hit_count = Column(Integer, nullable=False, default=0, server_default="0", comment="被检索命中次数")

    enabled = Column(Boolean, nullable=False, default=False, server_default=text("0"), comment="是否启用")
    disabled_at = Column(DateTime, nullable=True, comment="禁用时间")

    processing_started_at = Column(DateTime, nullable=True)
    indexing_completed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    stopped_at = Column(DateTime, nullable=True)

    error = Column(Text, nullable=False, default="", server_default="", comment="错误信息")
    status = Column(
        String(32), nullable=False, default="waiting", server_default="waiting",
        comment="对齐 SegmentStatus: waiting/indexing/completed/error",
    )

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class KeywordTable(db.Model):
    """知识库关键词倒排表：一个 dataset 一行 {keyword: [segment_id,...]}，供全文检索。"""

    __tablename__ = "ai_keyword_table"
    __table_args__ = (
        Index("ix_ai_keyword_table_dataset_id", "dataset_id", unique=True),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, nullable=False, comment="所属知识库（唯一）")
    keyword_table = Column(JSON, nullable=False, default=dict, server_default=text("('{}')"), comment="{keyword: [segment_id,...]}")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class DatasetQuery(db.Model):
    """知识库查询历史。"""

    __tablename__ = "ai_dataset_query"
    __table_args__ = (
        Index("ix_ai_dataset_query_dataset_id", "dataset_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, nullable=False, comment="被查询的知识库")
    query = Column(Text, nullable=False, default="", server_default="", comment="查询语句")
    source = Column(
        String(32), nullable=False, default="hit_testing", server_default="hit_testing",
        comment="来源：hit_testing / app（对齐 RetrievalSource）",
    )
    source_app_id = Column(Integer, nullable=True, comment="来源应用 id（app 来源时填）")
    created_by = Column(Integer, nullable=True, comment="发起者账号 id")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProcessRule(db.Model):
    """文档切分规则。"""

    __tablename__ = "ai_process_rule"
    __table_args__ = (
        Index("ix_ai_process_rule_dataset_id", "dataset_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, nullable=False, comment="归属账号 id（= account.id）",
    )
    dataset_id = Column(Integer, nullable=False, comment="所属知识库")
    mode = Column(
        String(32), nullable=False, default="custom", server_default="custom",
        comment="处理模式：automatic / custom（对齐 ProcessType）",
    )
    rule = Column(JSON, nullable=False, default=dict, server_default=text("('{}')"), comment="{pre_process_rules, segment:{chunk_size,chunk_overlap,separators}}")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
