"""文档相关 Celery 任务（异步索引 + 启停/删除善后）。

任务体只做"取 IndexingService → 委托"，injector/服务在函数内延迟 import，避免与 service 层的导入环。
FlaskTask（celery_extension）已包 app_context，worker 内可直接用 db / Qdrant / 模型。
"""
from typing import List

from celery import shared_task


# acks_late + reject_on_worker_lost：任务在执行完成后才 ack，worker 被 OOM(SIGKILL)杀死时
# 这条在途任务会被重新投递，配合 IndexingService 的幂等重建 + redis 重试上限，避免文档永久卡在「索引中」。
@shared_task(name="ai.build_documents", acks_late=True, reject_on_worker_lost=True)
def build_documents(document_ids: List[int]) -> None:
    from app.http.module import injector
    from internal.service.indexing_service import IndexingService

    injector.get(IndexingService).build_documents(document_ids)


@shared_task(name="ai.update_document_enabled")
def update_document_enabled(document_id: int, enabled: bool) -> None:
    from app.http.module import injector
    from internal.service.indexing_service import IndexingService

    injector.get(IndexingService).update_document_enabled(document_id, enabled)


@shared_task(name="ai.delete_document")
def delete_document(dataset_id: int, document_id: int, segment_ids: List[int]) -> None:
    from app.http.module import injector
    from internal.service.indexing_service import IndexingService

    injector.get(IndexingService).delete_document(dataset_id, document_id, segment_ids)
