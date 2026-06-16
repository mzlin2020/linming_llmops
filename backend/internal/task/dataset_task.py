"""知识库相关 Celery 任务（删除善后：清向量库 + 旁路表行）。"""
from celery import shared_task


@shared_task(name="ai.delete_dataset")
def delete_dataset(dataset_id: int) -> None:
    from app.http.module import injector
    from internal.service.indexing_service import IndexingService

    injector.get(IndexingService).delete_dataset(dataset_id)
