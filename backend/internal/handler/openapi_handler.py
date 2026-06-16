"""开放 API handler——通过 API key 鉴权（openapi 蓝图），非 JWT。

鉴权已由 openapi 蓝图分支（middleware._load_by_api_key）完成，故**不加 @RequireLogin**：
访问 current_user 即触发该分支，缺/无效/停用 key 会抛 401，current_user = 钥匙归属人。
单端点双模式：compact_generate_response 处理「生成器→SSE / Response→JSON」。
"""
from dataclasses import dataclass

from flask import request
from flask_login import current_user
from injector import inject
from pydantic import ValidationError

from internal.exception import ValidateErrorException
from internal.lib.helper import first_validation_error
from internal.schema.openapi_schema import OpenAPIAppInfoReq, OpenAPIChatReq
from internal.service import OpenAPIService
from pkg.response import compact_generate_response, success


@inject
@dataclass
class OpenAPIHandler:
    openapi_service: OpenAPIService

    def chat(self):
        """POST /api/openapi/chat —— 开放 API 聊天（stream=true 走 SSE；stream=false 一次性返回）。"""
        # 先触发 API key 鉴权（openapi 蓝图分支）：无效/缺失/停用 key 在此抛 401，
        # 早于参数校验与业务逻辑（否则不存在的 app_id 会先抛 404 而非 401）。
        account = current_user._get_current_object()
        try:
            req = OpenAPIChatReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=first_validation_error(e))
        return compact_generate_response(self.openapi_service.chat(req, account))

    def app_info(self):
        """GET /api/openapi/app-info?app_id= —— 已发布应用对外元信息（开场白/开场建议问题）。

        纯读配置、不触发 LLM 调用——开放新端点前先想清楚：任何会产生模型调用的
        开放 API 端点都意味着新的对外成本/滥用面，须经限流与归属隔离评审。
        """
        account = current_user._get_current_object()
        try:
            req = OpenAPIAppInfoReq.model_validate(request.args.to_dict(flat=True))
        except ValidationError as e:
            raise ValidateErrorException(message=first_validation_error(e))
        return success(self.openapi_service.app_info(account, req.app_id))
