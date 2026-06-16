"""ApiToolHandler：自定义 API 工具 / 插件的 CRUD + OpenAPI 校验（按 user_id 归属隔离）。

全部要求登录。请求体用 pydantic v2 解析（ValidationError → ValidateErrorException），
响应用 pkg.response 的 success / success_message 包裹，对齐 conversation_handler 风格。
"""
from dataclasses import dataclass

from flask import request
from flask_login import current_user
from injector import inject
from pydantic import ValidationError

from internal.exception import ValidateErrorException
from internal.lib.helper import first_validation_error as _first_error
from internal.middleware import RequireLogin
from internal.schema.api_tool_schema import (
    CreateApiToolReq,
    GetApiToolProvidersWithPageReq,
    PublishApiToolReq,
    UpdateApiToolProviderReq,
    ValidateOpenAPISchemaReq,
)
from internal.service import ApiToolService
from pkg.response import success, success_message


@inject
@dataclass
class ApiToolHandler:
    api_tool_service: ApiToolService

    @RequireLogin
    def get_api_tool_providers_with_page(self):
        """GET /api/api-tools —— 当前用户的自定义工具提供者分页列表（支持 search_word）。"""
        try:
            req = GetApiToolProvidersWithPageReq.model_validate(request.args.to_dict(flat=True))
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        return success(self.api_tool_service.get_api_tool_providers_with_page(req, current_user))

    @RequireLogin
    def create_api_tool_provider(self):
        """POST /api/api-tools —— 上传 OpenAPI schema 创建工具提供者。"""
        try:
            req = CreateApiToolReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        self.api_tool_service.create_api_tool(req, current_user)
        return success_message("创建自定义 API 插件成功")

    @RequireLogin
    def update_api_tool_provider(self, provider_id: int):
        """POST /api/api-tools/<provider_id> —— 覆盖式更新工具提供者及其工具。"""
        try:
            req = UpdateApiToolProviderReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        self.api_tool_service.update_api_tool_provider(provider_id, req, current_user)
        return success_message("更新自定义 API 插件成功")

    @RequireLogin
    def get_api_tool_provider(self, provider_id: int):
        """GET /api/api-tools/<provider_id> —— 工具提供者原始信息（含 openapi_schema）。"""
        return success(self.api_tool_service.get_api_tool_provider(provider_id, current_user))

    @RequireLogin
    def get_api_tool(self, provider_id: int, tool_name: str):
        """GET /api/api-tools/<provider_id>/tools/<tool_name> —— 单个工具参数详情。"""
        return success(self.api_tool_service.get_api_tool(provider_id, tool_name, current_user))

    @RequireLogin
    def delete_api_tool_provider(self, provider_id: int):
        """POST /api/api-tools/<provider_id>/delete —— 删除工具提供者及其工具。"""
        self.api_tool_service.delete_api_tool_provider(provider_id, current_user)
        return success_message("删除自定义 API 插件成功")

    @RequireLogin
    def validate_openapi_schema(self):
        """POST /api/api-tools/validate-openapi-schema —— 校验 OpenAPI schema 合法性。"""
        try:
            req = ValidateOpenAPISchemaReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        self.api_tool_service.parse_openapi_schema(req.openapi_schema)
        return success_message("数据校验成功")

    # ---------- 公共插件商店 ----------

    @RequireLogin
    def get_plugin_store(self):
        """GET /api/plugin-store —— 公共插件商店分页列表（含「是否已添加」标记）。"""
        try:
            req = GetApiToolProvidersWithPageReq.model_validate(request.args.to_dict(flat=True))
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        return success(self.api_tool_service.get_plugin_store_with_page(req, current_user))

    @RequireLogin
    def publish_api_tool_provider(self, provider_id: int):
        """POST /api/api-tools/<provider_id>/publish —— 发布 / 取消发布到商店（任意登录用户，仅限自己的插件）。"""
        try:
            req = PublishApiToolReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        self.api_tool_service.set_provider_public(provider_id, req.is_public, current_user)
        return success_message("发布到商店成功" if req.is_public else "已从商店下架")

    @RequireLogin
    def add_plugin_to_me(self, public_id: int):
        """POST /api/plugin-store/<public_id>/add —— 复制一份公共插件到我的插件列表。"""
        self.api_tool_service.add_plugin_to_me(public_id, current_user)
        return success_message("已添加到我的插件")
