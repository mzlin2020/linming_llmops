"""Python 代码执行节点（管理员专属）。

三道闸的最后一道：草稿宽松校验剔除（service 层）→ 发布严格校验拒绝（WorkflowConfig）
→ 本节点运行时 double-check is_admin。沙箱细节见 code_executor.py。
"""
import time
from typing import Optional

from langchain_core.runnables import RunnableConfig

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.variable_entity import VARIABLE_TYPE_DEFAULT_VALUE_MAP
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes.base_node import BaseNode
from internal.core.workflow.utils.helper import extract_variables_from_state, get_config_int
from internal.exception import FailException, ForbiddenException

from .code_entity import CodeNodeData
from .code_executor import execute_code


class CodeNode(BaseNode):
    """Python 代码运行节点。代码必须是单个 ``def main(params)`` 函数，返回字典。"""

    node_data: CodeNodeData

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        # 运行时权限闸（防止旧数据/绕过编排校验的图带入 code 节点）
        if not self.is_admin:
            raise ForbiddenException(message="Code 节点为管理员专属能力")

        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        try:
            result = execute_code(
                self.node_data.code,
                inputs_dict,
                timeout_seconds=get_config_int("WORKFLOW_CODE_TIMEOUT_SECONDS", 5),
                max_output_bytes=get_config_int("WORKFLOW_CODE_MAX_OUTPUT_BYTES", 65536),
            )
        except ValueError as e:
            raise FailException(message=f"Python代码执行出错：{e}")

        # 按声明的输出变量提取（非严格：缺失给类型默认值）
        outputs_dict = {}
        for output in self.node_data.outputs:
            outputs_dict[output.name] = result.get(
                output.name,
                VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(output.type),
            )

        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=inputs_dict,
                    outputs=outputs_dict,
                    latency=(time.perf_counter() - start_at),
                )
            ]
        }
