"""WorkflowService：工作流 CRUD + 草稿/发布双轨 + 调试 SSE + chat 工具装配。

生命周期：
  存草稿（宽松校验，坏节点/坏边静默剔除，重置 is_debug_passed）
  → 调试（严格校验 + 真实运行，SSE 逐节点推 NodeResult，跑通置 is_debug_passed）
  → 发布（要求 is_debug_passed + 严格二次校验，draft_graph 拷入 graph）
  → 应用绑定（app_config.workflows 存 id 列表）
  → 对话装配（get_langchain_tools_by_ids 实时按 已发布+归属 过滤）。

代码节点策略（本平台无管理员概念）：工作流相关校验/构建一律按 is_admin=True 放行，
即代码节点（Python 三层沙箱）对所有登录用户开放；副作用是工作流内 admin_only 内置工具节点
亦随之放行——与「单运维自托管」一致（详见 SECURITY.md）。

SSE 纪律（项目硬约束）：返回 generator 前完成全部校验/构造/ORM 快照，并先落
ai_workflow_result(running) 行；流式期间零 DB 操作；finally 单次 auto_commit 收尾。
"""
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Generator, Optional

from injector import inject
from sqlalchemy import desc, func
from sqlalchemy.orm import load_only

from internal.core.agent.tool_resolver import find_owned_api_tools
from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.core.workflow import WorkflowConfig, WorkflowTool
from internal.core.workflow.entities.node_entity import BaseNodeData, NodeType
from internal.core.workflow.entities.edge_entity import BaseEdgeData
from internal.core.workflow.nodes import NODE_DATA_CLASSES
from internal.core.workflow.nodes.dataset_retrieval.dataset_retrieval_entity import MAX_DATASETS_PER_NODE
from internal.entity.chat_entity import QueueEvent
from internal.entity.workflow_entity import (
    DEFAULT_WORKFLOW_CONFIG,
    WORKFLOW_TOOL_NAME_PREFIX,
    WorkflowResultStatus,
    WorkflowStatus,
)
from internal.exception import ForbiddenException, NotFoundException, ValidateErrorException
from internal.extension.database_extension import db
from internal.model import Account, Dataset, Workflow, WorkflowResult
from internal.schema.workflow_schema import CreateWorkflowReq, UpdateWorkflowReq, serialize_workflow
from internal.service._chat_common import sse
from internal.service.quota_service import QuotaService
from pkg.paginator import Paginator

# 代码节点对所有登录用户开放（本平台无管理员概念）：工作流校验/构建一律按此放行。
_WORKFLOW_IS_ADMIN = True


@inject
@dataclass
class WorkflowService:
    quota_service: QuotaService
    builtin_provider_manager: BuiltinProviderManager

    # ---------- CRUD ----------

    def create_workflow(self, user: Account, req: CreateWorkflowReq) -> Workflow:
        self.quota_service.check_create_workflow(user)
        self._check_tool_call_name_unique(user, req.tool_call_name)

        workflow = Workflow(
            user_id=user.id,
            name=req.name,
            tool_call_name=req.tool_call_name,
            icon=req.icon,
            description=req.description,
            status=WorkflowStatus.DRAFT.value,
            **DEFAULT_WORKFLOW_CONFIG,
        )
        with db.auto_commit():
            db.session.add(workflow)
        return workflow

    def get_workflow(self, workflow_id: int, user: Account) -> Workflow:
        workflow = db.session.get(Workflow, workflow_id)
        if workflow is None:
            raise NotFoundException(message="该工作流不存在，请核实后重试")
        if workflow.user_id != user.id:
            raise ForbiddenException(message="无权限访问该工作流")
        return workflow

    def update_workflow(self, workflow_id: int, user: Account, req: UpdateWorkflowReq) -> None:
        workflow = self.get_workflow(workflow_id, user)
        if req.tool_call_name is not None and req.tool_call_name != workflow.tool_call_name:
            self._check_tool_call_name_unique(user, req.tool_call_name, exclude_id=workflow.id)

        with db.auto_commit():
            if req.name is not None:
                workflow.name = req.name
            if req.tool_call_name is not None:
                workflow.tool_call_name = req.tool_call_name
            if req.icon is not None:
                workflow.icon = req.icon
            if req.description is not None:
                workflow.description = req.description

    def delete_workflow(self, workflow_id: int, user: Account) -> None:
        workflow = self.get_workflow(workflow_id, user)
        # 运行历史经 FK CASCADE 连带删除
        with db.auto_commit():
            db.session.delete(workflow)

    def get_workflows_with_page(
        self,
        current_page: int,
        page_size: int,
        search_word: Optional[str],
        status: Optional[str],
        user: Account,
    ) -> dict:
        query = db.session.query(Workflow).filter(Workflow.user_id == user.id)
        if search_word:
            query = query.filter(Workflow.name.like(f"%{search_word}%"))
        if status:
            query = query.filter(Workflow.status == status)

        paginator = Paginator(page=current_page, page_size=page_size, total_record=query.count())
        # MySQL（生产/CI 基准）：列表只取轻量列，节点数在 SQL 侧用 json_length 计算——不为 node_count
        # 加载整个 graph/draft_graph JSON。SQLite（本机测试代跑）无 json_length，回退取整行让
        # serialize_workflow 从 draft_graph 数节点（页大小 <=50，开销可忽略）。MySQL 行为不变。
        if db.session.get_bind().dialect.name == "mysql":
            rows = (
                query.options(load_only(
                    Workflow.id, Workflow.name, Workflow.tool_call_name, Workflow.icon,
                    Workflow.description, Workflow.status, Workflow.is_debug_passed,
                    Workflow.published_at, Workflow.created_at, Workflow.updated_at,
                ))
                .add_columns(func.coalesce(func.json_length(Workflow.draft_graph, "$.nodes"), 0))
                .order_by(desc(Workflow.created_at))
                .offset(paginator.offset)
                .limit(page_size)
                .all()
            )
            paginator.items = [serialize_workflow(row, node_count=int(node_count)) for row, node_count in rows]
        else:
            rows = (
                query.order_by(desc(Workflow.created_at))
                .offset(paginator.offset)
                .limit(page_size)
                .all()
            )
            paginator.items = [serialize_workflow(row) for row in rows]
        return paginator.to_dict()

    # ---------- 草稿图 ----------

    def get_draft_graph(self, workflow_id: int, user: Account) -> dict:
        """取草稿图（宽松校验后回传，并为 tool/dataset 节点附展示 meta）。"""
        workflow = self.get_workflow(workflow_id, user)
        draft_graph = self._validate_graph(workflow.draft_graph or {}, user)

        # meta 数据源批量预取（api_tool / dataset 各一条查询，替代逐节点 N+1）
        api_tool_map = self._prefetch_api_tool_rows(draft_graph["nodes"], user)
        dataset_map = self._prefetch_dataset_rows(draft_graph["nodes"], user)

        for node in draft_graph["nodes"]:
            if node.get("node_type") == NodeType.TOOL:
                node["meta"] = self._build_tool_meta(node, api_tool_map)
            elif node.get("node_type") == NodeType.DATASET_RETRIEVAL:
                node["meta"] = {"datasets": self._build_dataset_meta(node.get("dataset_ids") or [], dataset_map)}

        return draft_graph

    def update_draft_graph(self, workflow_id: int, draft_graph: dict, user: Account) -> None:
        """存草稿图：宽松校验（坏项剔除）后落库，并重置调试通过标记。"""
        workflow = self.get_workflow(workflow_id, user)
        validated = self._validate_graph(draft_graph or {}, user)

        with db.auto_commit():
            workflow.draft_graph = validated
            workflow.is_debug_passed = False

    # ---------- 调试（SSE） ----------

    def debug_workflow(self, workflow_id: int, inputs: dict, user: Account) -> Generator[str, None, None]:
        """调试运行草稿图。返回 SSE generator：event: workflow 帧 ×N（每节点一帧）。

        进流前完成：归属校验 → 调试配额 → 严格校验（失败 422 不进流）→ 工具构造 →
        ORM 快照 → 预落 result(running) 行。
        """
        workflow = self.get_workflow(workflow_id, user)
        self.quota_service.check_workflow_debug(user)

        draft_graph = workflow.draft_graph or {}
        tool = self._build_workflow_tool(workflow, user, draft_graph)  # 严格校验在此触发

        # 快照 ORM 属性为普通值（generator 跑在视图返回之后）
        wf_id = workflow.id
        user_id = user.id

        with db.auto_commit():
            result = WorkflowResult(
                app_id=None,
                user_id=user_id,
                workflow_id=wf_id,
                graph=draft_graph,
                state=[],
                latency=0,
                status=WorkflowResultStatus.RUNNING.value,
            )
            db.session.add(result)
        result_id = result.id

        def gen() -> Generator[str, None, None]:
            start_at = time.perf_counter()
            node_results_json: list[dict] = []
            run_status = WorkflowResultStatus.SUCCEEDED

            try:
                for chunk in tool.stream(inputs):
                    node_flag = next(iter(chunk))
                    node_results = chunk[node_flag].get("node_results") or []
                    if not node_results:
                        continue
                    payload = node_results[0].model_dump(mode="json", by_alias=True)
                    payload["id"] = str(uuid.uuid4())
                    node_results_json.append(payload)
                    yield sse(QueueEvent.WORKFLOW, payload)
            except Exception as e:
                run_status = WorkflowResultStatus.FAILED
                logging.warning("工作流调试运行失败：workflow_id=%s（%s）", wf_id, e)
                yield sse(QueueEvent.ERROR, {"message": str(e)[:500]})
            finally:
                # 单次收尾提交：result 行写终态；跑通则点亮发布闸门
                try:
                    row = db.session.get(WorkflowResult, result_id)
                    wf_row = db.session.get(Workflow, wf_id)
                    with db.auto_commit():
                        if row is not None:
                            row.state = node_results_json
                            row.latency = time.perf_counter() - start_at
                            row.status = run_status.value
                        if run_status == WorkflowResultStatus.SUCCEEDED and wf_row is not None:
                            wf_row.is_debug_passed = True
                except Exception:
                    logging.exception("工作流调试收尾落库失败：result_id=%s", result_id)

        return gen()

    # ---------- 发布 / 取消发布 ----------

    def publish_workflow(self, workflow_id: int, user: Account) -> None:
        workflow = self.get_workflow(workflow_id, user)
        if not workflow.is_debug_passed:
            raise ValidateErrorException(message="该工作流未调试通过，请先调试通过后发布")

        # 严格二次校验（草稿在调试后可能又被改坏；失败重置闸门）
        try:
            self._build_workflow_config(workflow, user, workflow.draft_graph or {})
        except Exception:
            with db.auto_commit():
                workflow.is_debug_passed = False
            raise ValidateErrorException(message="工作流配置校验失败，请重新调试通过后发布")

        with db.auto_commit():
            workflow.graph = workflow.draft_graph
            workflow.status = WorkflowStatus.PUBLISHED.value
            workflow.published_at = datetime.utcnow()
            workflow.is_debug_passed = False

    def cancel_publish_workflow(self, workflow_id: int, user: Account) -> None:
        workflow = self.get_workflow(workflow_id, user)
        if workflow.status != WorkflowStatus.PUBLISHED.value:
            raise ValidateErrorException(message="该工作流未发布，无法取消发布")

        # 绑定它的应用配置不级联清理：对话装配时按 PUBLISHED 实时过滤，自然失效
        with db.auto_commit():
            workflow.graph = {}
            workflow.status = WorkflowStatus.DRAFT.value
            workflow.published_at = None
            workflow.is_debug_passed = False

    # ---------- chat 装配 ----------

    def get_langchain_tools_by_ids(self, workflow_ids: list[int], user: Account) -> list:
        """按 id 批量构建工作流工具（chat 热路径）。

        单条查询 + 实时过滤（已发布 + 归属本人）；单条构造失败跳过并 warning，
        绝不让对话失败。WorkflowTool 惰性编译，本函数只有 pydantic 校验成本。
        """
        if not workflow_ids:
            return []

        records = (
            db.session.query(Workflow)
            .filter(
                Workflow.id.in_(workflow_ids),
                Workflow.user_id == user.id,
                Workflow.status == WorkflowStatus.PUBLISHED.value,
            )
            .all()
        )

        tools = []
        for record in records:
            try:
                tools.append(self._build_workflow_tool(record, user, record.graph or {}))
            except Exception as e:
                logging.warning("工作流工具构建失败，已跳过：workflow_id=%s（%s）", record.id, e)
        return tools

    # ---------- internal ----------

    def _build_workflow_config(self, workflow: Workflow, user: Account, graph: dict) -> WorkflowConfig:
        """严格校验图并产出 WorkflowConfig（校验失败抛 ValidateErrorException）。"""
        return WorkflowConfig(
            user_id=workflow.user_id,
            is_admin=_WORKFLOW_IS_ADMIN,
            name=f"{WORKFLOW_TOOL_NAME_PREFIX}{workflow.tool_call_name}",
            description=workflow.description or workflow.name,
            nodes=(graph or {}).get("nodes", []),
            edges=(graph or {}).get("edges", []),
        )

    def _build_workflow_tool(self, workflow: Workflow, user: Account, graph: dict) -> WorkflowTool:
        return WorkflowTool(self._build_workflow_config(workflow, user, graph))

    def _check_tool_call_name_unique(self, user: Account, tool_call_name: str, exclude_id: Optional[int] = None) -> None:
        query = db.session.query(Workflow.id).filter(
            Workflow.user_id == user.id,
            Workflow.tool_call_name == tool_call_name,
        )
        if exclude_id is not None:
            query = query.filter(Workflow.id != exclude_id)
        if query.first() is not None:
            raise ValidateErrorException(message="该工具调用名已被使用，请更换后重试")

    def _validate_graph(self, graph: dict, user: Account) -> dict:
        """宽松校验：逐 node/edge 校验，坏项静默剔除（编辑器中间态不报错）。

        额外清洗（安全）：
        - dataset_retrieval：dataset_ids 截断（MAX_DATASETS_PER_NODE，实体校验器执行）并按归属过滤；
        - tool(builtin)：admin_only 工具非超管剔除整个节点；
        - tool(api)：归属过滤（引用他人插件的节点剔除）；
        - code：代码节点对所有登录用户开放（is_admin 恒 True，故不剔除）。
        """
        is_admin = _WORKFLOW_IS_ADMIN
        nodes = graph.get("nodes", []) if isinstance(graph, dict) else []
        edges = graph.get("edges", []) if isinstance(graph, dict) else []

        # 归属数据批量预取（dataset / api_tool 各一条 IN 查询，替代逐节点 N+1——编辑器 600ms 防抖自动保存会频繁打到这里）
        owned_dataset_ids, owned_api_pairs = self._prefetch_owned_refs(nodes, user)

        node_data_dict: dict = {}
        start_count = 0
        end_count = 0
        for node in nodes:
            try:
                if not isinstance(node, dict):
                    continue
                node_type = node.get("node_type", "")
                node_data_cls = NODE_DATA_CLASSES.get(node_type)
                if node_data_cls is None:
                    continue

                # code 节点：is_admin 恒 True（对所有登录用户开放），不再剔除
                if node_type == NodeType.CODE and not is_admin:
                    continue

                node_data: BaseNodeData = node_data_cls(**node)

                # 开始/结束节点只保留第一个
                if node_data.node_type == NodeType.START:
                    if start_count >= 1:
                        continue
                    start_count += 1
                elif node_data.node_type == NodeType.END:
                    if end_count >= 1:
                        continue
                    end_count += 1

                # id / title 重复的剔除
                if node_data.id in node_data_dict:
                    continue
                if any(item.title.strip() == node_data.title.strip() for item in node_data_dict.values()):
                    continue

                # 知识库节点：归属过滤（数量上限由实体校验器按 MAX_DATASETS_PER_NODE 截断）
                if node_data.node_type == NodeType.DATASET_RETRIEVAL:
                    node_data.dataset_ids = [i for i in node_data.dataset_ids if i in owned_dataset_ids]

                # 工具节点：admin_only / 归属闸
                if node_data.node_type == NodeType.TOOL and not self._tool_node_allowed(node_data, is_admin, owned_api_pairs):
                    continue

                node_data_dict[node_data.id] = node_data
            except Exception:
                continue

        edge_data_dict: dict = {}
        for edge in edges:
            try:
                if not isinstance(edge, dict):
                    continue
                edge_data = BaseEdgeData(**edge)
                if edge_data.id in edge_data_dict:
                    continue
                # 起止节点必须存在且类型对得上
                if (
                    edge_data.source not in node_data_dict
                    or edge_data.source_type != node_data_dict[edge_data.source].node_type
                    or edge_data.target not in node_data_dict
                    or edge_data.target_type != node_data_dict[edge_data.target].node_type
                ):
                    continue
                # 边唯一（source+target）
                if any(
                    (item.source == edge_data.source and item.target == edge_data.target)
                    for item in edge_data_dict.values()
                ):
                    continue
                edge_data_dict[edge_data.id] = edge_data
            except Exception:
                continue

        return {
            "nodes": [node.model_dump(mode="json", by_alias=True) for node in node_data_dict.values()],
            "edges": [edge.model_dump(mode="json") for edge in edge_data_dict.values()],
        }

    @staticmethod
    def _api_pair(node: dict) -> Optional[tuple[int, str]]:
        """从原始 node dict 提取 api_tool 的 (provider_id, 工具名) 键；非法返回 None。"""
        try:
            return int(node.get("provider_id")), str(node.get("tool_id"))
        except (TypeError, ValueError):
            return None

    def _prefetch_owned_refs(self, nodes: list, user: Account) -> tuple[set, set]:
        """宽松校验前的归属预取：返回 (归属 dataset id 集合, 归属 api_tool (provider_id, name) 集合)。"""
        dataset_ids: set = set()
        api_pairs: set = set()
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get("node_type") == NodeType.DATASET_RETRIEVAL:
                ids = node.get("dataset_ids") or []
                if isinstance(ids, list):
                    dataset_ids.update(i for i in ids[:MAX_DATASETS_PER_NODE] if isinstance(i, int))
            elif node.get("node_type") == NodeType.TOOL and node.get("type") == "api_tool":
                pair = self._api_pair(node)
                if pair is not None:
                    api_pairs.add(pair)

        owned_dataset_ids: set = set()
        if dataset_ids:
            owned_dataset_ids = {
                row.id for row in db.session.query(Dataset.id)
                .filter(Dataset.id.in_(dataset_ids), Dataset.user_id == user.id)
                .all()
            }
        owned_api_pairs = {
            (row.provider_id, row.name)
            for row in find_owned_api_tools(sorted(api_pairs), user.id)
        }
        return owned_dataset_ids, owned_api_pairs

    def _tool_node_allowed(self, node_data, is_admin: bool, owned_api_pairs: set) -> bool:
        """工具节点的保存侧闸门：admin_only 内置工具、他人 API 插件直接剔除。"""
        if node_data.tool_type == "builtin_tool":
            provider = self.builtin_provider_manager.get_provider(node_data.provider_id)
            if provider is None:
                return False
            if getattr(provider.provider_entity, "admin_only", False) and not is_admin:
                return False
            return provider.get_tool_entity(node_data.tool_id) is not None
        if node_data.tool_type == "api_tool":
            try:
                return (int(node_data.provider_id), str(node_data.tool_id)) in owned_api_pairs
            except (TypeError, ValueError):
                return False
        return False

    def _prefetch_api_tool_rows(self, nodes: list[dict], user: Account) -> dict:
        """tool(api) 节点的行批量预取：一条 joinedload(provider) 查询，键 (provider_id, name)。"""
        pairs = set()
        for node in nodes:
            if node.get("node_type") == NodeType.TOOL and node.get("type") == "api_tool":
                pair = self._api_pair(node)
                if pair is not None:
                    pairs.add(pair)
        rows = find_owned_api_tools(sorted(pairs), user.id, with_provider=True)
        return {(row.provider_id, row.name): row for row in rows}

    def _prefetch_dataset_rows(self, nodes: list[dict], user: Account) -> dict:
        """dataset_retrieval 节点的行批量预取：一条 IN 查询，键 dataset id。"""
        ids: set = set()
        for node in nodes:
            if node.get("node_type") == NodeType.DATASET_RETRIEVAL:
                ids.update(node.get("dataset_ids") or [])
        if not ids:
            return {}
        rows = db.session.query(Dataset).filter(Dataset.id.in_(ids), Dataset.user_id == user.id).all()
        return {row.id: row for row in rows}

    def _build_tool_meta(self, node: dict, api_tool_map: dict) -> dict:
        """tool 节点的展示 meta（编辑器回显用）。api_tool 行来自 _prefetch_api_tool_rows。"""
        meta = {"type": node.get("type"), "provider": {}, "tool": {}}
        try:
            if node.get("type") == "builtin_tool":
                provider = self.builtin_provider_manager.get_provider(node.get("provider_id"))
                if provider is not None:
                    entity = provider.provider_entity
                    tool_entity = provider.get_tool_entity(node.get("tool_id"))
                    meta["provider"] = {
                        "id": entity.name,
                        "name": entity.name,
                        "label": entity.label,
                        "icon": f"/api/builtin-tools/{entity.name}/icon",
                    }
                    if tool_entity is not None:
                        meta["tool"] = {"id": tool_entity.name, "name": tool_entity.name, "label": tool_entity.label}
            else:
                row = api_tool_map.get(self._api_pair(node))
                if row is not None:
                    meta["provider"] = {"id": row.provider_id, "name": row.provider.name, "icon": row.provider.icon}
                    meta["tool"] = {"id": row.id, "name": row.name, "label": row.name}
        except Exception:
            pass
        return meta

    def _build_dataset_meta(self, dataset_ids: list[int], dataset_map: dict) -> list[dict]:
        """dataset 节点的展示 meta。行来自 _prefetch_dataset_rows（已含归属过滤）。"""
        rows = (dataset_map.get(i) for i in dataset_ids)
        return [{"id": row.id, "name": row.name, "icon": row.icon} for row in rows if row is not None]
