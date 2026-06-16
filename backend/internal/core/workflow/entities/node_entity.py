"""工作流节点基础实体（pydantic v2）。

节点 id 是前端编辑器生成的 UUID（与 DB 的 int 主键无关），title 在图内唯一。
"""
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NodeType(str, Enum):
    """节点类型枚举。新增节点类型时同步登记 nodes/__init__.py 的两张注册表。"""

    START = "start"
    LLM = "llm"
    TOOL = "tool"
    CODE = "code"
    DATASET_RETRIEVAL = "dataset_retrieval"
    HTTP_REQUEST = "http_request"
    TEMPLATE_TRANSFORM = "template_transform"
    END = "end"


class BaseNodeData(BaseModel):
    """基础节点数据。"""

    class Position(BaseModel):
        """节点在画布上的坐标。"""

        x: float = 0
        y: float = 0

    model_config = ConfigDict(populate_by_name=True)

    id: UUID  # 节点 id，图内唯一
    node_type: NodeType
    title: str = ""  # 节点标题，图内唯一
    description: str = ""
    position: Position = Field(default_factory=Position)


class NodeStatus(str, Enum):
    """节点运行状态。"""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class NodeResult(BaseModel):
    """单个节点的运行结果（调试 SSE 逐帧推送的就是它）。"""

    node_data: BaseNodeData
    status: NodeStatus = NodeStatus.RUNNING
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    latency: float = 0
    error: str = ""
