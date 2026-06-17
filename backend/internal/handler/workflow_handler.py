"""WorkflowHandler：工作流 CRUD + 草稿图 + 调试(SSE) + 发布生命周期（按 user_id 归属隔离）。

全部要求登录。请求体用 pydantic v2 解析，响应用 pkg.response.success / success_message 包裹；
调试端点返回 text/event-stream（前端 nginx 反代 /api 已配 proxy_buffering off）。
"""
from dataclasses import dataclass

from flask import request
from flask_login import current_user
from injector import inject
from pydantic import ValidationError

from internal.exception import ValidateErrorException
from internal.lib.helper import first_validation_error as _first_error
from internal.middleware import RequireLogin
from internal.schema.workflow_schema import (
    CreateWorkflowReq,
    GetWorkflowsWithPageReq,
    UpdateWorkflowReq,
    serialize_workflow,
)
from internal.service import WorkflowService
from pkg.response import compact_generate_response, success, success_message


@inject
@dataclass
class WorkflowHandler:
    workflow_service: WorkflowService

    @RequireLogin
    def get_workflows_with_page(self):
        """GET /api/workflows —— 当前用户工作流分页列表（支持 search_word / status 过滤）。"""
        try:
            req = GetWorkflowsWithPageReq.model_validate(request.args.to_dict(flat=True))
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        return success(self.workflow_service.get_workflows_with_page(
            req.current_page, req.page_size, req.search_word, req.status, current_user,
        ))

    @RequireLogin
    def create_workflow(self):
        """POST /api/workflows —— 创建工作流。"""
        try:
            req = CreateWorkflowReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        workflow = self.workflow_service.create_workflow(current_user, req)
        return success({"id": workflow.id})

    @RequireLogin
    def get_workflow(self, workflow_id: int):
        """GET /api/workflows/<workflow_id> —— 工作流详情。"""
        workflow = self.workflow_service.get_workflow(workflow_id, current_user)
        return success(serialize_workflow(workflow))

    @RequireLogin
    def update_workflow(self, workflow_id: int):
        """POST /api/workflows/<workflow_id> —— 更新基础信息。"""
        try:
            req = UpdateWorkflowReq.model_validate(request.get_json(silent=True) or {})
        except ValidationError as e:
            raise ValidateErrorException(message=_first_error(e))
        self.workflow_service.update_workflow(workflow_id, current_user, req)
        return success_message("更新工作流成功")

    @RequireLogin
    def delete_workflow(self, workflow_id: int):
        """POST /api/workflows/<workflow_id>/delete —— 删除工作流（级联清运行历史）。"""
        self.workflow_service.delete_workflow(workflow_id, current_user)
        return success_message("删除工作流成功")

    @RequireLogin
    def get_draft_graph(self, workflow_id: int):
        """GET /api/workflows/<workflow_id>/draft-graph —— 取草稿图（含展示 meta）。"""
        return success(self.workflow_service.get_draft_graph(workflow_id, current_user))

    @RequireLogin
    def update_draft_graph(self, workflow_id: int):
        """POST /api/workflows/<workflow_id>/draft-graph —— 存草稿图（宽松校验，重置调试标记）。"""
        body = request.get_json(silent=True) or {}
        draft_graph = {
            "nodes": body.get("nodes") or [],
            "edges": body.get("edges") or [],
        }
        self.workflow_service.update_draft_graph(workflow_id, draft_graph, current_user)
        return success_message("保存草稿成功")

    @RequireLogin
    def debug_workflow(self, workflow_id: int):
        """POST /api/workflows/<workflow_id>/debug —— 调试运行（SSE，每节点一帧）。

        请求体即工作流入参 {var: value, ...}。
        """
        body = request.get_json(silent=True)
        inputs = body if isinstance(body, dict) else {}
        gen = self.workflow_service.debug_workflow(workflow_id, inputs, current_user)
        return compact_generate_response(gen)

    @RequireLogin
    def publish_workflow(self, workflow_id: int):
        """POST /api/workflows/<workflow_id>/publish —— 发布（要求调试通过）。"""
        self.workflow_service.publish_workflow(workflow_id, current_user)
        return success_message("发布工作流成功")

    @RequireLogin
    def cancel_publish_workflow(self, workflow_id: int):
        """POST /api/workflows/<workflow_id>/cancel-publish —— 取消发布。"""
        self.workflow_service.cancel_publish_workflow(workflow_id, current_user)
        return success_message("取消发布成功")
