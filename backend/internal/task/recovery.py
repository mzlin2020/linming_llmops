"""Celery worker 启动恢复钩子。

worker 启动时（含被 OOM/异常杀死后由 `restart: on-failure` 拉起、或正常部署重启），
扫描卡在中间态(parsing/splitting/indexing)且超阈值无进展的文档并复位为 error，
作为 acks_late 自动重投之外的兜底——确保任何残留都不会永久停在「索引中」。
"""
import logging

from celery.signals import worker_ready


@worker_ready.connect
def _recover_stuck_documents_on_boot(**_) -> None:
    try:
        from app.http.app import app
        from app.http.module import injector
        from internal.service.indexing_service import IndexingService

        with app.app_context():
            count = injector.get(IndexingService).recover_stuck_documents()
        if count:
            logging.warning("[recovery] worker 启动复位卡死文档 %s 个", count)
    except Exception:  # 恢复失败绝不能让 worker 起不来
        logging.exception("[recovery] worker 启动复位卡死文档失败")
