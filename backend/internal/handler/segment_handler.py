"""SegmentHandler：文档片段 CRUD + 启停（按 user_id 归属隔离）。手动操作同步更新向量库与关键词表。"""
from dataclasses import dataclass

from flask import request
from flask_login import current_user
from injector import inject
from pydantic import ValidationError

from internal.exception import ValidateErrorException
from internal.middleware import RequireLogin
from internal.schema.dataset_schema import (
    CreateSegmentReq,
    GetSegmentsWithPageReq,
    UpdateSegmentEnabledReq,
    UpdateSegmentReq,
)
from internal.service import SegmentService
from pkg.response import success, success_message
from internal.lib.helper import first_validation_error as _first_error


@inject
@dataclass
class SegmentHandler:
    segment_service: SegmentService

    @RequireLogin
    def get_segments_with_page(self, dataset_id: int, document_id: int):
        """GET /api/datasets/<dataset_id>/documents/<document_id>/segments —— 片段分页列表。"""
        try:
            req = GetSegmentsWithPageReq.model_validate(request.args.to_dict(flat=True))
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        return success(self.segment_service.get_segments_with_page(current_user, dataset_id, document_id, req))

    @RequireLogin
    def create_segment(self, dataset_id: int, document_id: int):
        """POST /api/datasets/<dataset_id>/documents/<document_id>/segments —— 手动新增片段。"""
        try:
            req = CreateSegmentReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        return success(self.segment_service.create_segment(
            current_user, dataset_id, document_id, req.content, req.keywords,
        ))

    @RequireLogin
    def get_segment(self, dataset_id: int, document_id: int, segment_id: int):
        """GET /api/datasets/<dataset_id>/documents/<document_id>/segments/<segment_id> —— 片段详情。"""
        return success(self.segment_service.get_segment(current_user, dataset_id, document_id, segment_id))

    @RequireLogin
    def update_segment(self, dataset_id: int, document_id: int, segment_id: int):
        """POST /api/datasets/<dataset_id>/documents/<document_id>/segments/<segment_id> —— 改片段内容。"""
        try:
            req = UpdateSegmentReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        return success(self.segment_service.update_segment(
            current_user, dataset_id, document_id, segment_id, req.content, req.keywords,
        ))

    @RequireLogin
    def update_segment_enabled(self, dataset_id: int, document_id: int, segment_id: int):
        """POST /api/datasets/<dataset_id>/documents/<document_id>/segments/<segment_id>/enabled —— 启停。"""
        try:
            req = UpdateSegmentEnabledReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        self.segment_service.update_segment_enabled(
            current_user, dataset_id, document_id, segment_id, req.enabled,
        )
        return success_message("更新片段状态成功")

    @RequireLogin
    def delete_segment(self, dataset_id: int, document_id: int, segment_id: int):
        """POST /api/datasets/<dataset_id>/documents/<document_id>/segments/<segment_id>/delete —— 删除片段。"""
        self.segment_service.delete_segment(current_user, dataset_id, document_id, segment_id)
        return success_message("删除片段成功")
