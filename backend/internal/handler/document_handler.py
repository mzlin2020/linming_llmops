"""DocumentHandler：知识库文档 CRUD + 批量上传建文档 + 批次状态轮询（按 user_id 归属隔离）。"""
from dataclasses import dataclass

from flask import request
from flask_login import current_user
from injector import inject
from pydantic import ValidationError

from internal.exception import ValidateErrorException
from internal.middleware import RequireLogin
from internal.schema.dataset_schema import (
    CreateDocumentsReq,
    GetDocumentsWithPageReq,
    UpdateDocumentEnabledReq,
    UpdateDocumentNameReq,
)
from internal.service import DocumentService
from pkg.response import success, success_message
from internal.lib.helper import first_validation_error as _first_error


@inject
@dataclass
class DocumentHandler:
    document_service: DocumentService

    @RequireLogin
    def get_documents_with_page(self, dataset_id: int):
        """GET /api/datasets/<dataset_id>/documents —— 文档分页列表。"""
        try:
            req = GetDocumentsWithPageReq.model_validate(request.args.to_dict(flat=True))
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        return success(self.document_service.get_documents_with_page(
            dataset_id, req.current_page, req.page_size, req.search_word, current_user,
        ))

    @RequireLogin
    def create_documents(self, dataset_id: int):
        """POST /api/datasets/<dataset_id>/documents —— 用上传文件批量建文档并触发异步索引。"""
        try:
            req = CreateDocumentsReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        return success(self.document_service.create_documents(
            dataset_id, req.upload_file_ids, current_user, req.process_type, req.rule,
        ))

    @RequireLogin
    def get_document(self, dataset_id: int, document_id: int):
        """GET /api/datasets/<dataset_id>/documents/<document_id> —— 文档详情。"""
        return success(self.document_service.get_document(dataset_id, document_id, current_user))

    @RequireLogin
    def update_document_name(self, dataset_id: int, document_id: int):
        """POST /api/datasets/<dataset_id>/documents/<document_id>/name —— 改名。"""
        try:
            req = UpdateDocumentNameReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        self.document_service.update_document_name(dataset_id, document_id, req.name, current_user)
        return success_message("更新文档名称成功")

    @RequireLogin
    def update_document_enabled(self, dataset_id: int, document_id: int):
        """POST /api/datasets/<dataset_id>/documents/<document_id>/enabled —— 启停。"""
        try:
            req = UpdateDocumentEnabledReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        self.document_service.update_document_enabled(dataset_id, document_id, req.enabled, current_user)
        return success_message("更新文档状态成功")

    @RequireLogin
    def delete_document(self, dataset_id: int, document_id: int):
        """POST /api/datasets/<dataset_id>/documents/<document_id>/delete —— 删除（异步清向量）。"""
        self.document_service.delete_document(dataset_id, document_id, current_user)
        return success_message("删除文档成功")

    @RequireLogin
    def reindex_document(self, dataset_id: int, document_id: int):
        """POST /api/datasets/<dataset_id>/documents/<document_id>/re-index —— 重新索引（终态文档复位重建）。"""
        self.document_service.reindex_document(dataset_id, document_id, current_user)
        return success_message("已重新发起索引")

    @RequireLogin
    def get_documents_status(self, dataset_id: int, batch: str):
        """GET /api/datasets/<dataset_id>/documents/batch/<batch> —— 批次内文档处理状态。"""
        return success(self.document_service.get_documents_status(dataset_id, batch, current_user))
