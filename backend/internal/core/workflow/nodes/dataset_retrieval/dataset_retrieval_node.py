"""知识库检索节点：复用 retrieval_service 的 dataset_retrieval 工具。

归属安全：检索工具内部按 ``Dataset.user_id == user_id`` 二次过滤（图保存时
service 层已按归属清洗过 dataset_ids，这里是运行时兜底）。工具懒构建 +
ensure_app_context()，原因同 ToolNode。
"""
import time
from typing import Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from pydantic import PrivateAttr

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes.base_node import BaseNode
from internal.core.workflow.utils.helper import extract_variables_from_state
from internal.exception import FailException

from .dataset_retrieval_entity import DatasetRetrievalNodeData


class DatasetRetrievalNode(BaseNode):
    """知识库检索节点。"""

    node_data: DatasetRetrievalNodeData
    _retrieval_tool: Optional[BaseTool] = PrivateAttr(default=None)

    def _resolve_tool(self) -> BaseTool:
        if self._retrieval_tool is not None:
            return self._retrieval_tool

        if self.user_id is None:
            raise FailException(message="知识库节点缺少归属用户，无法执行检索")

        from app.http.module import injector
        from internal.entity.dataset_entity import RetrievalSource
        from internal.service.retrieval_service import RetrievalService

        self._retrieval_tool = injector.get(RetrievalService).create_langchain_tool_from_search(
            dataset_ids=self.node_data.dataset_ids,
            user_id=self.user_id,
            retrieval_strategy=self.node_data.retrieval_config.retrieval_strategy.value,
            k=self.node_data.retrieval_config.k,
            score=self.node_data.retrieval_config.score,
            source=RetrievalSource.APP.value,
        )
        return self._retrieval_tool

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        with self.ensure_app_context():
            tool = self._resolve_tool()
            combine_documents = tool.invoke(inputs_dict)

        outputs = {}
        if self.node_data.outputs:
            outputs[self.node_data.outputs[0].name] = combine_documents
        else:
            outputs["combine_documents"] = combine_documents

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
