"""节点注册表：新增节点类型 = 新增一个目录 + 在两张表里各登记一行。

NODE_DATA_CLASSES 供严格/宽松校验实例化节点数据；NODE_CLASSES 供 WorkflowTool
构建 LangGraph 图时实例化可执行节点。两表 key 都是 NodeType（str 枚举，
字符串可直接命中）。
"""
from internal.core.workflow.entities.node_entity import NodeType

from .base_node import BaseNode
from .code import CodeNode, CodeNodeData
from .dataset_retrieval import DatasetRetrievalNode, DatasetRetrievalNodeData
from .end import EndNode, EndNodeData
from .http_request import HttpRequestNode, HttpRequestNodeData
from .llm import LLMNode, LLMNodeData
from .start import StartNode, StartNodeData
from .template_transform import TemplateTransformNode, TemplateTransformNodeData
from .tool import ToolNode, ToolNodeData

# 节点数据类注册表（校验用）
NODE_DATA_CLASSES: dict[NodeType, type] = {
    NodeType.START: StartNodeData,
    NodeType.END: EndNodeData,
    NodeType.LLM: LLMNodeData,
    NodeType.TEMPLATE_TRANSFORM: TemplateTransformNodeData,
    NodeType.DATASET_RETRIEVAL: DatasetRetrievalNodeData,
    NodeType.CODE: CodeNodeData,
    NodeType.TOOL: ToolNodeData,
    NodeType.HTTP_REQUEST: HttpRequestNodeData,
}

# 节点执行类注册表（图构建用）
NODE_CLASSES: dict[NodeType, type[BaseNode]] = {
    NodeType.START: StartNode,
    NodeType.END: EndNode,
    NodeType.LLM: LLMNode,
    NodeType.TEMPLATE_TRANSFORM: TemplateTransformNode,
    NodeType.DATASET_RETRIEVAL: DatasetRetrievalNode,
    NodeType.CODE: CodeNode,
    NodeType.TOOL: ToolNode,
    NodeType.HTTP_REQUEST: HttpRequestNode,
}

__all__ = [
    "BaseNode",
    "NODE_CLASSES",
    "NODE_DATA_CLASSES",
    "StartNode", "StartNodeData",
    "LLMNode", "LLMNodeData",
    "TemplateTransformNode", "TemplateTransformNodeData",
    "DatasetRetrievalNode", "DatasetRetrievalNodeData",
    "CodeNode", "CodeNodeData",
    "ToolNode", "ToolNodeData",
    "HttpRequestNode", "HttpRequestNodeData",
    "EndNode", "EndNodeData",
]
