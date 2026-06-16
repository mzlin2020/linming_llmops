from dataclasses import dataclass

from flask import Blueprint, Flask
from injector import inject

from internal.handler import (
    AccountHandler,
    AuthHandler,
    DatasetHandler,
    DocumentHandler,
    PingHandler,
    SegmentHandler,
    UploadFileHandler,
)


@inject
@dataclass
class Router:
    ping_handler: PingHandler
    auth_handler: AuthHandler
    account_handler: AccountHandler
    upload_file_handler: UploadFileHandler
    dataset_handler: DatasetHandler
    document_handler: DocumentHandler
    segment_handler: SegmentHandler

    def register_router(self, app: Flask):
        bp = Blueprint("api", __name__, url_prefix="/api")

        # 健康检查（public）
        bp.add_url_rule("/ping", view_func=self.ping_handler.ping, methods=["GET"])

        # 认证（public）
        bp.add_url_rule("/auth/register", view_func=self.auth_handler.register, methods=["POST"])
        bp.add_url_rule("/auth/login", view_func=self.auth_handler.login, methods=["POST"])
        bp.add_url_rule("/auth/refresh", view_func=self.auth_handler.refresh, methods=["POST"])
        bp.add_url_rule("/auth/logout", view_func=self.auth_handler.logout, methods=["POST"])

        # 账号（需登录）
        bp.add_url_rule("/account/me", view_func=self.account_handler.me, methods=["GET"])

        # ---------- 知识库：文件上传 ----------
        bp.add_url_rule("/upload-files/file",
                        view_func=self.upload_file_handler.upload_file, methods=["POST"])

        # ---------- 知识库：dataset CRUD + 命中测试 + 查询历史 ----------
        bp.add_url_rule("/datasets",
                        view_func=self.dataset_handler.get_datasets_with_page, methods=["GET"])
        bp.add_url_rule("/datasets", endpoint="create_dataset",
                        view_func=self.dataset_handler.create_dataset, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>",
                        view_func=self.dataset_handler.get_dataset, methods=["GET"])
        bp.add_url_rule("/datasets/<int:dataset_id>", endpoint="update_dataset",
                        view_func=self.dataset_handler.update_dataset, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>/delete",
                        view_func=self.dataset_handler.delete_dataset, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>/hit",
                        view_func=self.dataset_handler.hit, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>/queries",
                        view_func=self.dataset_handler.get_dataset_queries, methods=["GET"])

        # ---------- 知识库：文档（注意 /documents/batch/<batch> 的 batch 为静态段，与 <int:document_id> 不冲突） ----------
        bp.add_url_rule("/datasets/<int:dataset_id>/documents",
                        view_func=self.document_handler.get_documents_with_page, methods=["GET"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents", endpoint="create_documents",
                        view_func=self.document_handler.create_documents, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/batch/<string:batch>",
                        view_func=self.document_handler.get_documents_status, methods=["GET"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>",
                        view_func=self.document_handler.get_document, methods=["GET"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>/name",
                        view_func=self.document_handler.update_document_name, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>/enabled",
                        view_func=self.document_handler.update_document_enabled, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>/delete",
                        view_func=self.document_handler.delete_document, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>/re-index",
                        view_func=self.document_handler.reindex_document, methods=["POST"])

        # ---------- 知识库：片段 ----------
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>/segments",
                        view_func=self.segment_handler.get_segments_with_page, methods=["GET"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>/segments",
                        endpoint="create_segment",
                        view_func=self.segment_handler.create_segment, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>/segments/<int:segment_id>",
                        view_func=self.segment_handler.get_segment, methods=["GET"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>/segments/<int:segment_id>",
                        endpoint="update_segment",
                        view_func=self.segment_handler.update_segment, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>/segments/<int:segment_id>/enabled",
                        view_func=self.segment_handler.update_segment_enabled, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>/segments/<int:segment_id>/delete",
                        view_func=self.segment_handler.delete_segment, methods=["POST"])

        app.register_blueprint(bp)
