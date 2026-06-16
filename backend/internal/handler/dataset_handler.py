"""DatasetHandler：知识库 CRUD + 命中测试 + 查询历史（按 user_id 归属隔离）。

全部要求登录。请求体用 pydantic v2 解析，响应用 pkg.response.success / success_message 包裹。
"""
from dataclasses import dataclass

from flask import request
from flask_login import current_user
from injector import inject
from pydantic import ValidationError

from internal.exception import ValidateErrorException
from internal.middleware import RequireLogin
from internal.schema.dataset_schema import (
    CreateDatasetReq,
    GetDatasetsWithPageReq,
    HitReq,
    UpdateDatasetReq,
)
from internal.service import DatasetService
from pkg.response import success, success_message
from internal.lib.helper import first_validation_error as _first_error


@inject
@dataclass
class DatasetHandler:
    dataset_service: DatasetService

    @RequireLogin
    def get_datasets_with_page(self):
        """GET /api/datasets —— 当前用户知识库分页列表（支持 search_word）。"""
        try:
            req = GetDatasetsWithPageReq.model_validate(request.args.to_dict(flat=True))
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        return success(self.dataset_service.get_datasets_with_page(
            req.current_page, req.page_size, req.search_word, current_user,
        ))

    @RequireLogin
    def create_dataset(self):
        """POST /api/datasets —— 创建知识库。"""
        try:
            req = CreateDatasetReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        ds = self.dataset_service.create_dataset(req.name, req.icon, req.description, current_user)
        return success({"id": ds.id})

    @RequireLogin
    def get_dataset(self, dataset_id: int):
        """GET /api/datasets/<dataset_id> —— 知识库详情（含统计量）。"""
        return success(self.dataset_service.get_dataset(dataset_id, current_user))

    @RequireLogin
    def update_dataset(self, dataset_id: int):
        """POST /api/datasets/<dataset_id> —— 更新知识库元信息。"""
        try:
            req = UpdateDatasetReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        self.dataset_service.update_dataset(dataset_id, req.name, req.icon, req.description, current_user)
        return success_message("更新知识库成功")

    @RequireLogin
    def delete_dataset(self, dataset_id: int):
        """POST /api/datasets/<dataset_id>/delete —— 删除知识库（异步清向量库）。"""
        self.dataset_service.delete_dataset(dataset_id, current_user)
        return success_message("删除知识库成功")

    @RequireLogin
    def hit(self, dataset_id: int):
        """POST /api/datasets/<dataset_id>/hit —— 命中测试（检索）。"""
        try:
            req = HitReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        return success(self.dataset_service.hit(
            dataset_id, req.query, current_user, req.retrieval_strategy, req.k, req.score,
        ))

    @RequireLogin
    def get_dataset_queries(self, dataset_id: int):
        """GET /api/datasets/<dataset_id>/queries —— 最近查询记录。"""
        return success(self.dataset_service.get_dataset_queries(dataset_id, current_user))
