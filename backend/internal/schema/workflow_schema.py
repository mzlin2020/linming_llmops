"""工作流接口的请求/响应 schema（pydantic v2）。"""
from typing import Optional

from pydantic import BaseModel, Field

from internal.core.workflow.entities.variable_entity import VARIABLE_NAME_PATTERN
from internal.lib.helper import datetime_to_timestamp

# tool_call_name 规则与核心层标识符规则同源（单一出处在 variable_entity）
TOOL_CALL_NAME_PATTERN = VARIABLE_NAME_PATTERN


class CreateWorkflowReq(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    tool_call_name: str = Field(min_length=1, max_length=64, pattern=TOOL_CALL_NAME_PATTERN)
    icon: str = Field(default="", max_length=512)
    # 描述是给 LLM 的工具说明，必填
    description: str = Field(min_length=1, max_length=1024)


class UpdateWorkflowReq(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    tool_call_name: Optional[str] = Field(
        default=None, min_length=1, max_length=64, pattern=TOOL_CALL_NAME_PATTERN
    )
    icon: Optional[str] = Field(default=None, max_length=512)
    description: Optional[str] = Field(default=None, min_length=1, max_length=1024)


class GetWorkflowsWithPageReq(BaseModel):
    current_page: int = Field(default=1, ge=1, le=9999)
    page_size: int = Field(default=20, ge=1, le=50)
    search_word: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None, pattern=r"^(draft|published)?$")


def serialize_workflow(row, node_count: Optional[int] = None) -> dict:
    """ai_workflow 行 → 列表/详情响应 dict。

    node_count 可由列表查询在 SQL 侧预计算后传入（避免为数节点数加载整个 draft_graph JSON）；
    不传时回退从行上的 draft_graph 计算（详情场景）。"""
    if node_count is None:
        node_count = len((row.draft_graph or {}).get("nodes") or [])
    return {
        "id": row.id,
        "name": row.name,
        "tool_call_name": row.tool_call_name,
        "icon": row.icon,
        "description": row.description,
        "status": row.status,
        "is_debug_passed": bool(row.is_debug_passed),
        "node_count": node_count,
        "published_at": datetime_to_timestamp(row.published_at),
        "created_at": datetime_to_timestamp(row.created_at),
        "updated_at": datetime_to_timestamp(row.updated_at),
    }
