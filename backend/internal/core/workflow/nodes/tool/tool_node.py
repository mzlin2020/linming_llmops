"""扩展插件节点：调用内置工具或用户自定义 API 工具。

设计要点：
- 工具懒解析（首次 invoke 才查注册表/DB），配合 WorkflowTool 的惰性编译让 chat 装配零开销；
- builtin admin_only 工具加运行时闸（非超管拒绝）；
- api_tool 查询强制 ``ApiTool.user_id == self.user_id`` 归属过滤（只按 provider_id+name 查
  会有引用他人插件的越权洞，此处按归属用户收紧）；
- DB/注入器访问包在 ensure_app_context() 里（LangGraph worker 线程无 Flask 上下文）。
"""
import json
import time
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from pydantic import PrivateAttr

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes.base_node import BaseNode
from internal.core.workflow.utils.helper import extract_variables_from_state
from internal.exception import FailException, ForbiddenException, NotFoundException

from .tool_entity import ToolNodeData


class ToolNode(BaseNode):
    """扩展插件节点，涵盖内置插件与自定义 API 插件。"""

    node_data: ToolNodeData
    _tool: Optional[BaseTool] = PrivateAttr(default=None)

    def _resolve_tool(self) -> BaseTool:
        """懒解析工具实例（缓存在 _tool）。"""
        if self._tool is not None:
            return self._tool

        from app.http.module import injector

        if self.node_data.tool_type == "builtin_tool":
            from internal.core.agent.tool_resolver import instantiate_builtin_tool
            from internal.core.tools.builtin_tools.providers import BuiltinProviderManager

            manager = injector.get(BuiltinProviderManager)

            # admin_only 工具（如图像生成）运行时闸：非超管直接拒绝
            provider = manager.get_provider(self.node_data.provider_id)
            if (
                provider is not None
                and getattr(provider.provider_entity, "admin_only", False)
                and not self.is_admin
            ):
                raise ForbiddenException(message="该内置插件为管理员专属，请先移除后再操作")

            tool = instantiate_builtin_tool(
                manager, self.node_data.provider_id, self.node_data.tool_id, self.node_data.params
            )
            if tool is None:
                raise NotFoundException(message="该内置插件扩展不存在，请核实后重试")
            self._tool = tool
        else:
            from internal.core.agent.tool_resolver import build_api_tool_entity, find_owned_api_tool
            from internal.core.tools.api_tools.providers import ApiProviderManager

            try:
                provider_id = int(self.node_data.provider_id)
            except (TypeError, ValueError):
                raise NotFoundException(message="该API扩展插件不存在，请核实后重试")

            # 归属过滤：只允许调用自己的插件
            api_tool = find_owned_api_tool(
                provider_id, self.node_data.tool_id, self.user_id, with_provider=True
            )
            if not api_tool:
                raise NotFoundException(message="该API扩展插件不存在，请核实后重试")

            self._tool = injector.get(ApiProviderManager).get_tool(build_api_tool_entity(api_tool))

        if not isinstance(self._tool, BaseTool):
            raise FailException(message="扩展插件构造失败，请稍后尝试")
        return self._tool

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        with self.ensure_app_context():
            tool = self._resolve_tool()
            try:
                result: Any = tool.invoke(inputs_dict)
            except Exception:
                raise FailException(message="扩展插件执行失败，请稍后尝试")

        if not isinstance(result, str):
            result = json.dumps(result, ensure_ascii=False, default=str)

        outputs = {}
        if self.node_data.outputs:
            outputs[self.node_data.outputs[0].name] = result
        else:
            outputs["text"] = result

        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=inputs_dict,
                    outputs=outputs,
                    latency=(time.perf_counter() - start_at),
                )
            ]
        }
