"""模板转换节点：jinja2 沙箱渲染（防 SSTI）。"""
import time
from typing import Optional

from langchain_core.runnables import RunnableConfig

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes.base_node import BaseNode
from internal.core.workflow.utils.helper import extract_variables_from_state, render_template_sandboxed

from .template_transform_entity import TemplateTransformNodeData


class TemplateTransformNode(BaseNode):
    """模板转换节点，将多个变量合并成一个字符串。"""

    node_data: TemplateTransformNodeData

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        template_value = render_template_sandboxed(self.node_data.template, inputs_dict)

        outputs = {"output": template_value}

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
