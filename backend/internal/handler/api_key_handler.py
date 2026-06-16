"""开放 API 密钥管理 handler——账号自管自己的密钥（CRUD，JWT 保护，主蓝图）。"""
from dataclasses import dataclass

from flask import request
from flask_login import current_user
from injector import inject
from pydantic import ValidationError

from internal.exception import ValidateErrorException
from internal.lib.helper import first_validation_error
from internal.middleware import RequireLogin
from internal.schema.api_key_schema import CreateApiKeyReq, UpdateApiKeyReq
from internal.service import ApiKeyService
from pkg.response import success, success_message


def _key_view(k) -> dict:
    return {
        "id": k.id,
        "api_key": k.api_key,
        "is_active": bool(k.is_active),
        "remark": k.remark or "",
        "created_at": int(k.created_at.timestamp()) if k.created_at else 0,
        "updated_at": int(k.updated_at.timestamp()) if k.updated_at else 0,
    }


@inject
@dataclass
class ApiKeyHandler:
    api_key_service: ApiKeyService

    @RequireLogin
    def list_keys(self):
        """GET /api/api-keys —— 当前用户的密钥列表。"""
        keys = self.api_key_service.list_by_user(current_user)
        return success({"list": [_key_view(k) for k in keys]})

    @RequireLogin
    def create_key(self):
        """POST /api/api-keys —— 签发一把新密钥（返回明文串，请妥善保存）。"""
        try:
            req = CreateApiKeyReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=first_validation_error(e))
        k = self.api_key_service.create(current_user, remark=req.remark, is_active=req.is_active)
        return success(_key_view(k))

    @RequireLogin
    def update_key(self, key_id: int):
        """POST /api/api-keys/<key_id> —— 改备注 / 启停。"""
        try:
            req = UpdateApiKeyReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=first_validation_error(e))
        k = self.api_key_service.update(
            current_user, key_id, remark=req.remark, is_active=req.is_active,
        )
        return success(_key_view(k))

    @RequireLogin
    def delete_key(self, key_id: int):
        """POST /api/api-keys/<key_id>/delete —— 删除密钥。"""
        self.api_key_service.delete(current_user, key_id)
        return success_message("ok")
