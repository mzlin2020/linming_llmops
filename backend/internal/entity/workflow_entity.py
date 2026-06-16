"""工作流领域常量。"""
from enum import Enum


class WorkflowStatus(str, Enum):
    """工作流状态：draft 仅可编辑/调试，published 才能被应用绑定。"""

    DRAFT = "draft"
    PUBLISHED = "published"


class WorkflowResultStatus(str, Enum):
    """单次运行（调试/应用调用）的状态。"""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


# 新建工作流的默认配置：graph 为发布版（空 = 未发布），draft_graph 为编辑器草稿
DEFAULT_WORKFLOW_CONFIG = {
    "graph": {},
    "draft_graph": {"nodes": [], "edges": []},
}

# 暴露给 LLM 的工具名前缀：wf_{tool_call_name}，与内置/自定义工具名区隔
WORKFLOW_TOOL_NAME_PREFIX = "wf_"
