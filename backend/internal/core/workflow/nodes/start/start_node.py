"""开始节点：提取工作流输入并做必填校验。"""
import time
from typing import Optional

from langchain_core.runnables import RunnableConfig

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.variable_entity import VARIABLE_TYPE_DEFAULT_VALUE_MAP
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes.base_node import BaseNode
from internal.exception import FailException

from .start_entity import StartNodeData


class StartNode(BaseNode):
    """开始节点。"""

    node_data: StartNodeData

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        start_at = time.perf_counter()
        inputs = self.node_data.inputs

        # 逐个检查输入：必填缺失直接报错，非必填给类型默认值
        outputs = {}
        for input in inputs:
            input_value = state["inputs"].get(input.name, None)

            if input_value is None:
                if input.required:
                    raise FailException(message=f"工作流参数生成出错，{input.name}为必填参数")
                input_value = VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(input.type)

            outputs[input.name] = input_value

        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=state["inputs"],
                    outputs=outputs,
                    latency=(time.perf_counter() - start_at),
                )
            ]
        }
