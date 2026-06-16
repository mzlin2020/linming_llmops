"""知识库（RAG）请求 schema（pydantic v2）。

响应不另建 schema：service 直接组装 dict，handler 用 success(...) 包裹。
"""
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from internal.entity import ProcessType, RetrievalStrategy
from internal.schema.conversation_schema import PaginatorReq

_STRATEGIES = {s.value for s in RetrievalStrategy}
_PROCESS_TYPES = {t.value for t in ProcessType}


# ---------------- 知识库 ----------------

class _DatasetReq(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="知识库名")
    icon: str = Field(default="", max_length=512, description="图标 URL")
    description: str = Field(default="", max_length=2000, description="知识库描述")


class CreateDatasetReq(_DatasetReq):
    pass


class UpdateDatasetReq(_DatasetReq):
    pass


class GetDatasetsWithPageReq(PaginatorReq):
    search_word: Optional[str] = Field(default=None, description="按名称模糊搜索")


class HitReq(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="检索 query")
    retrieval_strategy: str = Field(default=RetrievalStrategy.SEMANTIC.value, description="semantic/full_text/hybrid")
    k: int = Field(default=4, ge=1, le=10, description="返回条数")
    score: float = Field(default=0.0, ge=0.0, le=0.99, description="语义检索最小相关度阈值")

    @field_validator("retrieval_strategy")
    @classmethod
    def check_strategy(cls, v):
        if v not in _STRATEGIES:
            raise ValueError("检索策略必须是 semantic / full_text / hybrid 之一")
        return v


# ---------------- 文档 ----------------

class CreateDocumentsReq(BaseModel):
    upload_file_ids: List[int] = Field(..., min_length=1, description="上传文件 id 列表")
    process_type: str = Field(default=ProcessType.AUTOMATIC.value, description="automatic/custom")
    rule: Optional[dict] = Field(default=None, description="custom 模式下的切分规则")

    @field_validator("process_type")
    @classmethod
    def check_process_type(cls, v):
        if v not in _PROCESS_TYPES:
            raise ValueError("处理模式必须是 automatic / custom")
        return v


class GetDocumentsWithPageReq(PaginatorReq):
    search_word: Optional[str] = Field(default=None, description="按名称模糊搜索")


class UpdateDocumentNameReq(BaseModel):
    name: str = Field(..., min_length=1, max_length=512, description="文档名")


class UpdateDocumentEnabledReq(BaseModel):
    enabled: bool = Field(..., description="是否启用")


# ---------------- 片段 ----------------

class GetSegmentsWithPageReq(PaginatorReq):
    pass


class CreateSegmentReq(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000, description="片段内容")
    keywords: Optional[List[str]] = Field(default=None, description="关键词（缺省则自动抽取）")


class UpdateSegmentReq(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000, description="片段内容")
    keywords: Optional[List[str]] = Field(default=None, description="关键词（缺省则自动抽取）")


class UpdateSegmentEnabledReq(BaseModel):
    enabled: bool = Field(..., description="是否启用")

    model_config = ConfigDict(extra="ignore")
