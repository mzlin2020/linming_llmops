"""工作流节点图运行时：用户画的 DAG → LangGraph 图程序 → LangChain 工具。

结构：entities/（配置与状态）+ nodes/（8 种节点，注册表式扩展）+
utils/（变量提取、沙箱模板）+ workflow.py（WorkflowTool，惰性编译）。
"""
from .entities.workflow_entity import WorkflowConfig, WorkflowState
from .workflow import WorkflowTool

__all__ = ["WorkflowConfig", "WorkflowState", "WorkflowTool"]
