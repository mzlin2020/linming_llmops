"""业务实体（枚举 / 默认配置 / 轻量 schema）。模型与 core 通过全路径 import 各自模块。"""
from .dataset_entity import (
    DEFAULT_MAX_KEYWORD_PER_CHUNK,
    DEFAULT_PROCESS_RULE,
    DEFAULT_RETRIEVAL_K,
    DEFAULT_RETRIEVAL_SCORE,
    DocumentStatus,
    ProcessType,
    RetrievalSource,
    RetrievalStrategy,
    SegmentStatus,
)

__all__ = [
    "RetrievalStrategy",
    "RetrievalSource",
    "ProcessType",
    "DocumentStatus",
    "SegmentStatus",
    "DEFAULT_MAX_KEYWORD_PER_CHUNK",
    "DEFAULT_RETRIEVAL_K",
    "DEFAULT_RETRIEVAL_SCORE",
    "DEFAULT_PROCESS_RULE",
]
