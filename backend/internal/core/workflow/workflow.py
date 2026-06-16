"""WorkflowTool：把整张工作流 DAG 封装成一个 LangChain BaseTool。

设计要点：
- 类名 WorkflowTool，避免与 internal.model.Workflow（DB 模型）撞名；
- 惰性编译：构造时只急构 args_schema（function calling 需要工具入参规格，开销极小），
  LangGraph 图的节点实例化 + compile 推迟到首次 _run/stream——chat 装配 N 个工作流
  工具时零节点构造/零 DB 查询，LLM 不调用则零成本；
- 构造时捕获 Flask app 引用，统一塞给所有节点（见 BaseNode.ensure_app_context）；
- 节点实例化走 NODE_CLASSES 注册表 + 统一上下文 kwargs，无 if/elif 链。
"""
import threading
from typing import Any, Iterator, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.utils import Input, Output
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr, create_model

from .entities.node_entity import NodeType
from .entities.variable_entity import VARIABLE_TYPE_MAP
from .entities.workflow_entity import WorkflowConfig, WorkflowState
from .nodes import NODE_CLASSES


class WorkflowTool(BaseTool):
    """工作流 LangChain 工具类。"""

    _workflow_config: WorkflowConfig = PrivateAttr()
    _flask_app: Optional[Any] = PrivateAttr(default=None)
    _compiled: Optional[Any] = PrivateAttr(default=None)
    _compile_lock: Any = PrivateAttr(default=None)

    def __init__(self, workflow_config: WorkflowConfig, **kwargs: Any):
        super().__init__(
            name=workflow_config.name,
            description=workflow_config.description,
            args_schema=self._build_args_schema(workflow_config),
            **kwargs,
        )
        self._workflow_config = workflow_config
        self._compile_lock = threading.Lock()

        # 捕获 Flask 应用引用：编译/执行可能发生在无上下文的 worker 线程
        try:
            from flask import current_app

            self._flask_app = current_app._get_current_object()
        except RuntimeError:
            self._flask_app = None

    @classmethod
    def _build_args_schema(cls, workflow_config: WorkflowConfig) -> type[BaseModel]:
        """从开始节点的 inputs 动态生成工具入参 schema（LLM 据此组装调用参数）。"""
        fields = {}
        inputs = next(
            (node.inputs for node in workflow_config.nodes if node.node_type == NodeType.START),
            [],
        )

        for input in inputs:
            field_type = VARIABLE_TYPE_MAP.get(input.type, str)
            if input.required:
                # pydantic v2：必填字段不给 default
                fields[input.name] = (field_type, Field(description=input.description))
            else:
                # pydantic v2：Optional 不再隐含默认值，必须显式 default=None
                fields[input.name] = (Optional[field_type], Field(default=None, description=input.description))

        return create_model("DynamicModel", **fields)

    def _graph(self):
        """惰性编译（双检锁防并发重复编译）。"""
        if self._compiled is None:
            with self._compile_lock:
                if self._compiled is None:
                    self._compiled = self._build_workflow()
        return self._compiled

    def _build_workflow(self):
        """把校验过的 nodes/edges 装配成 LangGraph 图程序并编译。"""
        from langgraph.graph import StateGraph

        graph = StateGraph(WorkflowState)

        config = self._workflow_config
        # 所有节点统一上下文：归属用户/超管标记/Flask 应用引用
        node_context = dict(
            user_id=config.user_id,
            is_admin=config.is_admin,
            flask_app=self._flask_app,
        )

        # 1.注册表驱动地添加节点
        for node in config.nodes:
            node_flag = f"{node.node_type.value}_{node.id}"
            node_cls = NODE_CLASSES[node.node_type]
            graph.add_node(node_flag, node_cls(node_data=node, **node_context))

        # 2.合并并行边（同一终点的多个起点合成一条多源边，扇入处自动等待）
        parallel_edges: dict[str, list[str]] = {}
        start_node = ""
        end_node = ""
        for edge in config.edges:
            source_node = f"{edge.source_type.value}_{edge.source}"
            target_node = f"{edge.target_type.value}_{edge.target}"
            parallel_edges.setdefault(target_node, []).append(source_node)

            # 两个独立 if：避免只有一条边时识别失败
            if edge.source_type == NodeType.START:
                start_node = source_node
            if edge.target_type == NodeType.END:
                end_node = target_node

        # 3.设置起点终点并添加边
        graph.set_entry_point(start_node)
        graph.set_finish_point(end_node)

        for target_node, source_nodes in parallel_edges.items():
            graph.add_edge(source_nodes, target_node)

        return graph.compile()

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """同步执行整条工作流，返回结束节点的 outputs。"""
        result = self._graph().invoke({"inputs": kwargs})
        return result.get("outputs", {})

    def stream(
        self,
        input: Input,
        config: Optional[RunnableConfig] = None,
        **kwargs: Optional[Any],
    ) -> Iterator[Output]:
        """流式执行：逐节点产出 {node_flag: {"node_results": [NodeResult]}}（调试 SSE 用）。"""
        return self._graph().stream({"inputs": input})
