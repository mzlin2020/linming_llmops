"""工作流配置与运行状态（pydantic v2 + int user_id）。

WorkflowConfig 是「严格校验」入口：调试与发布前都用它整体校验图结构
（唯一开始/结束、连通性、无环、变量引用合法）；草稿保存走 service 层的宽松校验。
WorkflowState 是 LangGraph 的黑板状态，Annotated reducer 支持并行分支合流。
"""
import re
from collections import defaultdict, deque
from typing import Annotated, Any, TypedDict
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from internal.exception import ValidateErrorException

from .edge_entity import BaseEdgeData
from .node_entity import BaseNodeData, NodeResult, NodeType
from .variable_entity import VARIABLE_NAME_PATTERN, VariableEntity, VariableValueType

# 工作流配置校验信息（名字规则与变量名同源，单一出处在 variable_entity）
WORKFLOW_CONFIG_NAME_PATTERN = VARIABLE_NAME_PATTERN
WORKFLOW_CONFIG_DESCRIPTION_MAX_LENGTH = 1024


def _max_nodes() -> int:
    """图节点数上限（4GB 主机防护）。优先 Flask 配置，无应用上下文时回退环境变量/默认值。"""
    # 函数内导入：utils 包会反向 import 本模块（helper 取 WorkflowState），模块顶导入会成环
    from internal.core.workflow.utils.config_read import get_config_int

    return get_config_int("WORKFLOW_MAX_NODES", 20)


def _process_dict(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """状态字典归纳函数（并行分支合流时合并）。"""
    left = left or {}
    right = right or {}
    return {**left, **right}


def _process_node_results(left: list[NodeResult], right: list[NodeResult]) -> list[NodeResult]:
    """节点结果列表归纳函数（并行分支合流时拼接）。"""
    left = left or []
    right = right or []
    return left + right


class WorkflowConfig(BaseModel):
    """工作流配置信息（严格校验）。"""

    user_id: int  # 工作流归属用户 id（共享 user 表的 int 主键）
    is_admin: bool = False  # 归属用户是否超管（code 节点等管理员专属能力的闸门）
    name: str = ""  # 工作流名称（即工具调用名，必须是英文标识符）
    description: str = ""  # 描述信息，告知 LLM 何时调用该工作流
    nodes: list[BaseNodeData] = Field(default_factory=list)
    edges: list[BaseEdgeData] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def validate_workflow_config(cls, values: dict[str, Any]) -> dict[str, Any]:
        """整体校验工作流配置：图结构 + 变量引用。"""
        # 1.校验工作流名字
        name = values.get("name", None)
        if not name or not re.match(WORKFLOW_CONFIG_NAME_PATTERN, name):
            raise ValidateErrorException(message="工作流名字仅支持字母、数字和下划线，且以字母/下划线为开头")

        # 2.校验描述信息（传递给 LLM 的工具描述）
        description = values.get("description", None)
        if not description or len(description) > WORKFLOW_CONFIG_DESCRIPTION_MAX_LENGTH:
            raise ValidateErrorException(message="工作流描述信息不能为空且长度不能超过1024个字符")

        # 3.获取节点和边列表信息
        nodes = values.get("nodes", [])
        edges = values.get("edges", [])

        # 4.校验 nodes/edges 数据类型和内容不能为空
        if not isinstance(nodes, list) or len(nodes) <= 0:
            raise ValidateErrorException(message="工作流节点列表信息错误，请核实后重试")
        if not isinstance(edges, list) or len(edges) <= 0:
            raise ValidateErrorException(message="工作流边列表信息错误，请核实后重试")

        # 5.图规模上限（4GB 主机防护）
        if len(nodes) > _max_nodes():
            raise ValidateErrorException(message=f"工作流节点数量不能超过{_max_nodes()}个")

        # 6.节点数据类从注册表取（新增节点类型零侵入）
        from internal.core.workflow.nodes import NODE_DATA_CLASSES

        is_admin = bool(values.get("is_admin", False))
        node_data_dict: dict[UUID, BaseNodeData] = {}
        start_nodes = 0
        end_nodes = 0
        for node in nodes:
            # 7.允许传入已实例化的 NodeData（宽松校验后的复用场景）
            if isinstance(node, BaseNodeData):
                node = node.model_dump(mode="json", by_alias=True)
            if not isinstance(node, dict):
                raise ValidateErrorException(message="工作流节点数据类型出错，请核实后重试")

            # 8.获取节点的类型并判断类型是否存在
            node_type = node.get("node_type", "")
            node_data_cls = NODE_DATA_CLASSES.get(node_type, None)
            if not node_data_cls:
                raise ValidateErrorException(message="工作流节点类型出错，请核实后重试")

            # 9.code 节点为管理员专属（与草稿宽松校验的剔除、CodeNode 构造闸构成三道防线）
            if node_type == NodeType.CODE and not is_admin:
                raise ValidateErrorException(message="Code 节点为管理员专属能力，请先移除后再操作")

            # 10.实例化节点数据，使用 BaseModel 规则进行校验
            node_data = node_data_cls(**node)

            # 11.判断开始和结束节点是否唯一
            if node_data.node_type == NodeType.START:
                if start_nodes >= 1:
                    raise ValidateErrorException(message="工作流中只允许有1个开始节点")
                start_nodes += 1
            elif node_data.node_type == NodeType.END:
                if end_nodes >= 1:
                    raise ValidateErrorException(message="工作流中只允许有1个结束节点")
                end_nodes += 1

            # 12.判断节点 id 是否唯一
            if node_data.id in node_data_dict:
                raise ValidateErrorException(message="工作流节点id必须唯一，请核实后重试")

            # 13.判断节点 title 是否唯一
            if any(item.title.strip() == node_data.title.strip() for item in node_data_dict.values()):
                raise ValidateErrorException(message="工作流节点title必须唯一，请核实后重试")

            node_data_dict[node_data.id] = node_data

        # 14.循环遍历 edges 数据
        edge_data_dict: dict[UUID, BaseEdgeData] = {}
        for edge in edges:
            if isinstance(edge, BaseEdgeData):
                edge = edge.model_dump(mode="json")
            if not isinstance(edge, dict):
                raise ValidateErrorException(message="工作流边数据类型出错，请核实后重试")

            # 15.实例化边数据，使用 BaseModel 规则进行校验
            edge_data = BaseEdgeData(**edge)

            # 16.校验边 id 是否唯一
            if edge_data.id in edge_data_dict:
                raise ValidateErrorException(message="工作流边数据id必须唯一，请核实后重试")

            # 17.校验边中的 source/target/source_type/target_type 必须和 nodes 对得上
            if (
                edge_data.source not in node_data_dict
                or edge_data.source_type != node_data_dict[edge_data.source].node_type
                or edge_data.target not in node_data_dict
                or edge_data.target_type != node_data_dict[edge_data.target].node_type
            ):
                raise ValidateErrorException(message="工作流边起点/终点对应的节点不存在或类型错误，请核实后重试")

            # 18.校验边必须唯一（source+target 唯一）
            if any(
                (item.source == edge_data.source and item.target == edge_data.target)
                for item in edge_data_dict.values()
            ):
                raise ValidateErrorException(message="工作流边数据不能重复添加")

            edge_data_dict[edge_data.id] = edge_data

        # 19.构建邻接表、逆邻接表、入度以及出度
        adj_list = cls._build_adj_list(list(edge_data_dict.values()))
        reverse_adj_list = cls._build_reverse_adj_list(list(edge_data_dict.values()))
        in_degree, out_degree = cls._build_degrees(list(edge_data_dict.values()))

        # 20.从边的关系中校验唯一的开始/结束节点（入度为0即开始，出度为0即结束）
        start_node_list = [node_data for node_data in node_data_dict.values() if in_degree[node_data.id] == 0]
        end_node_list = [node_data for node_data in node_data_dict.values() if out_degree[node_data.id] == 0]
        if (
            len(start_node_list) != 1
            or len(end_node_list) != 1
            or start_node_list[0].node_type != NodeType.START
            or end_node_list[0].node_type != NodeType.END
        ):
            raise ValidateErrorException(message="工作流中有且只有一个开始/结束节点作为图结构的起点和终点")

        start_node_data = start_node_list[0]

        # 21.校验图的连通性，确保没有孤立的节点
        if not cls._is_connected(adj_list, start_node_data.id):
            raise ValidateErrorException(message="工作流中存在不可到达节点，图不联通，请核实后重试")

        # 22.校验是否存在环路
        if cls._is_cycle(list(node_data_dict.values()), adj_list, in_degree):
            raise ValidateErrorException(message="工作流中存在环路，请核实后重试")

        # 23.校验 inputs/outputs 的引用数据是否指向前驱节点
        cls._validate_inputs_ref(node_data_dict, reverse_adj_list)

        # 24.更新 values 值
        values["nodes"] = list(node_data_dict.values())
        values["edges"] = list(edge_data_dict.values())

        return values

    @classmethod
    def _is_connected(cls, adj_list: defaultdict, start_node_id: UUID) -> bool:
        """BFS 检查从开始节点出发能否到达所有有边的节点。"""
        visited = set()
        queue = deque([start_node_id])
        visited.add(start_node_id)

        while queue:
            node_id = queue.popleft()
            for neighbor in adj_list[node_id]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        return len(visited) == len(adj_list)

    @classmethod
    def _is_cycle(
        cls,
        nodes: list[BaseNodeData],
        adj_list: defaultdict,
        in_degree: defaultdict,
    ) -> bool:
        """Kahn 拓扑排序检测环：访问次数小于总节点数即存在环。"""
        zero_in_degree_nodes = deque([node.id for node in nodes if in_degree[node.id] == 0])
        visited_count = 0

        while zero_in_degree_nodes:
            node_id = zero_in_degree_nodes.popleft()
            visited_count += 1
            for neighbor in adj_list[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    zero_in_degree_nodes.append(neighbor)

        return visited_count != len(nodes)

    @classmethod
    def _validate_inputs_ref(
        cls,
        node_data_dict: dict[UUID, BaseNodeData],
        reverse_adj_list: defaultdict,
    ) -> None:
        """校验 REF 类型变量必须引用前驱节点上确实存在的变量。"""
        for node_data in node_data_dict.values():
            predecessors = cls._get_predecessors(reverse_adj_list, node_data.id)

            if node_data.node_type != NodeType.START:
                # 结束节点校验 outputs，其余节点校验 inputs
                variables: list[VariableEntity] = (
                    node_data.inputs if node_data.node_type != NodeType.END else node_data.outputs
                )

                for variable in variables:
                    if variable.value.type == VariableValueType.REF:
                        # 引用节点必须是前驱
                        if (
                            len(predecessors) <= 0
                            or not isinstance(variable.value.content, VariableEntity.Value.Content)
                            or variable.value.content.ref_node_id not in predecessors
                        ):
                            raise ValidateErrorException(
                                message=f"工作流节点[{node_data.title}]引用数据出错，请核实后重试"
                            )

                        ref_node_data = node_data_dict.get(variable.value.content.ref_node_id)

                        # 开始节点取 inputs，其余节点取 outputs
                        ref_variables = (
                            ref_node_data.inputs if ref_node_data.node_type == NodeType.START
                            else ref_node_data.outputs
                        )

                        if not any(
                            ref_variable.name == variable.value.content.ref_var_name
                            for ref_variable in ref_variables
                        ):
                            raise ValidateErrorException(
                                message=f"工作流节点[{node_data.title}]引用了不存在的节点变量，请核实后重试"
                            )

    @classmethod
    def _build_adj_list(cls, edges: list[BaseEdgeData]) -> defaultdict:
        """邻接表：key 为节点 id，value 为其所有直接后继节点。"""
        adj_list = defaultdict(list)
        for edge in edges:
            adj_list[edge.source].append(edge.target)
            # 确保终点也出现在邻接表中（连通性按 len(adj_list) 比较）
            _ = adj_list[edge.target]
        return adj_list

    @classmethod
    def _build_reverse_adj_list(cls, edges: list[BaseEdgeData]) -> defaultdict:
        """逆邻接表：key 为节点 id，value 为其直接前驱节点。"""
        reverse_adj_list = defaultdict(list)
        for edge in edges:
            reverse_adj_list[edge.target].append(edge.source)
        return reverse_adj_list

    @classmethod
    def _build_degrees(cls, edges: list[BaseEdgeData]) -> tuple[defaultdict, defaultdict]:
        """计算每个节点的入度与出度。"""
        in_degree = defaultdict(int)
        out_degree = defaultdict(int)
        for edge in edges:
            in_degree[edge.target] += 1
            out_degree[edge.source] += 1
        return in_degree, out_degree

    @classmethod
    def _get_predecessors(cls, reverse_adj_list: defaultdict, target_node_id: UUID) -> list[UUID]:
        """沿逆邻接表 DFS，取目标节点的所有（直接+间接）前驱节点。"""
        visited = set()
        predecessors = []

        def dfs(node_id):
            if node_id not in visited:
                visited.add(node_id)
                if node_id != target_node_id:
                    predecessors.append(node_id)
                for neighbor in reverse_adj_list[node_id]:
                    dfs(neighbor)

        dfs(target_node_id)

        return predecessors


class WorkflowState(TypedDict):
    """工作流图程序状态字典（LangGraph 黑板）。"""

    inputs: Annotated[dict[str, Any], _process_dict]  # 工作流最初输入（即工具输入）
    outputs: Annotated[dict[str, Any], _process_dict]  # 工作流最终输出（仅结束节点写入）
    node_results: Annotated[list[NodeResult], _process_node_results]  # 各节点运行结果
