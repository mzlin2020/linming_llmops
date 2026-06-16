"""Celery 任务聚合。导入即注册 @shared_task / worker_ready 钩子。

含知识库（RAG）相关任务（Phase 4a）与对话收尾任务（Phase 4b：自动命名 + 长期记忆摘要）。
"""
from .dataset_task import delete_dataset
from .document_task import build_documents, delete_document, update_document_enabled
from .conversation_task import after_round_task
from . import recovery  # noqa: F401  导入即注册 worker_ready 启动恢复钩子

__all__ = [
    "build_documents",
    "update_document_enabled",
    "delete_document",
    "delete_dataset",
    "after_round_task",
]
