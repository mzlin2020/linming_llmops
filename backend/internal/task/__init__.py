"""Celery 任务聚合。导入即注册 @shared_task / worker_ready 钩子。

Phase 4a 仅含知识库（RAG）相关任务；对话 / 应用相关任务在后续阶段补充。
"""
from .dataset_task import delete_dataset
from .document_task import build_documents, delete_document, update_document_enabled
from . import recovery  # noqa: F401  导入即注册 worker_ready 启动恢复钩子

__all__ = [
    "build_documents",
    "update_document_enabled",
    "delete_document",
    "delete_dataset",
]
