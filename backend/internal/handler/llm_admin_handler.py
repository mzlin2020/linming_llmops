"""LlmAdminHandler：AI 模型目录（provider / model / channel）的管理后台 CRUD。

全部 @RequireLogin + service 层 _assert_llm_admin_enabled（部署级开关 ENABLE_LLM_ADMIN 守护，默认关）。
请求体走 pydantic v2，响应用 pkg.response.success / success_message 包裹。密钥只在请求体进、响应只回掩码。
"""
from dataclasses import dataclass

from flask import request
from flask_login import current_user
from injector import inject
from pydantic import ValidationError

from internal.exception import ValidateErrorException
from internal.lib.helper import first_validation_error as _first_error
from internal.middleware import RequireLogin
from internal.schema.llm_admin_schema import (
    CreateChannelReq,
    CreateModelReq,
    CreateProviderReq,
    UpdateChannelReq,
    UpdateModelReq,
    UpdateProviderReq,
)
from internal.service import LlmAdminService
from pkg.response import success, success_message


def _parse(model_cls):
    try:
        return model_cls.model_validate(request.get_json(silent=True) or {})
    except ValidationError as e:
        raise ValidateErrorException(message=_first_error(e))


@inject
@dataclass
class LlmAdminHandler:
    llm_admin_service: LlmAdminService

    # ---------- 协议 ----------
    @RequireLogin
    def list_protocols(self):
        """GET /api/admin/llm-protocols —— 当前可选的协议 key（供「协议」下拉）。"""
        return success(self.llm_admin_service.list_protocols(current_user))

    # ---------- provider ----------
    @RequireLogin
    def list_providers(self):
        """GET /api/admin/llm-providers —— 所有提供商（含禁用，key 掩码，含其 model/channel）。"""
        return success(self.llm_admin_service.list_providers(current_user))

    @RequireLogin
    def create_provider(self):
        """POST /api/admin/llm-providers"""
        return success(self.llm_admin_service.create_provider(_parse(CreateProviderReq), current_user))

    @RequireLogin
    def update_provider(self, provider_id: int):
        """POST /api/admin/llm-providers/<provider_id>"""
        return success(self.llm_admin_service.update_provider(provider_id, _parse(UpdateProviderReq), current_user))

    @RequireLogin
    def delete_provider(self, provider_id: int):
        """POST /api/admin/llm-providers/<provider_id>/delete"""
        self.llm_admin_service.delete_provider(provider_id, current_user)
        return success_message("删除提供商成功")

    # ---------- model ----------
    @RequireLogin
    def create_model(self, provider_id: int):
        """POST /api/admin/llm-providers/<provider_id>/models"""
        return success(self.llm_admin_service.create_model(provider_id, _parse(CreateModelReq), current_user))

    @RequireLogin
    def update_model(self, model_id: int):
        """POST /api/admin/llm-models/<model_id>"""
        return success(self.llm_admin_service.update_model(model_id, _parse(UpdateModelReq), current_user))

    @RequireLogin
    def delete_model(self, model_id: int):
        """POST /api/admin/llm-models/<model_id>/delete"""
        self.llm_admin_service.delete_model(model_id, current_user)
        return success_message("删除模型成功")

    # ---------- channel（仅 multi_channel provider）----------
    @RequireLogin
    def list_channels(self, provider_id: int):
        """GET /api/admin/llm-providers/<provider_id>/channels —— 渠道列表（含健康状态）。"""
        return success(self.llm_admin_service.list_channels(provider_id, current_user))

    @RequireLogin
    def create_channel(self, provider_id: int):
        """POST /api/admin/llm-providers/<provider_id>/channels"""
        return success(self.llm_admin_service.create_channel(provider_id, _parse(CreateChannelReq), current_user))

    @RequireLogin
    def update_channel(self, channel_id: int):
        """POST /api/admin/llm-channels/<channel_id>"""
        return success(self.llm_admin_service.update_channel(channel_id, _parse(UpdateChannelReq), current_user))

    @RequireLogin
    def delete_channel(self, channel_id: int):
        """POST /api/admin/llm-channels/<channel_id>/delete"""
        self.llm_admin_service.delete_channel(channel_id, current_user)
        return success_message("删除渠道成功")

    @RequireLogin
    def recover_channel(self, channel_id: int):
        """POST /api/admin/llm-channels/<channel_id>/recover —— 手动清掉熔断。"""
        self.llm_admin_service.recover_channel(channel_id, current_user)
        return success_message("渠道已恢复")
