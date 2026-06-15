"""自有表：工作流 2 张表。全部 ai_ 前缀。

- ai_workflow        —— 工作流本体：基础信息 + draft_graph（草稿）/ graph（发布版）双轨 +
                        is_debug_passed 发布闸门。 (user_id, tool_call_name) 唯一（service 校验 + DB 兜底）。
- ai_workflow_result —— 运行流水账（追加型）：每次调试/应用调用一行，graph 是当时的图快照，
                        state 是全部节点的 NodeResult 列表。app_id 为空 = 调试页直跑。

级联：workflow →(FK CASCADE) workflow_result，删工作流连带清运行历史。
user_id 是普通索引列（= account.id），不加 FK。
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)

from internal.extension.database_extension import db


class Workflow(db.Model):
    """工作流。"""

    __tablename__ = "ai_workflow"
    __table_args__ = (
        Index("ix_ai_workflow_user_id", "user_id"),
        UniqueConstraint("user_id", "tool_call_name", name="uq_ai_workflow_user_tool_call_name"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, nullable=False, comment="归属账号 id（= account.id）",
    )
    name = Column(String(64), nullable=False, default="", server_default="", comment="展示名")
    tool_call_name = Column(
        String(64), nullable=False, default="", server_default="",
        comment="工具调用名（英文标识符，同用户内唯一；暴露给 LLM 时加 wf_ 前缀）",
    )
    icon = Column(String(512), nullable=False, default="", server_default="", comment="图标 URL")
    description = Column(Text, nullable=False, comment="描述（给 LLM 判断何时调用）")
    graph = Column(JSON, nullable=False, default=dict, comment="发布版图配置（运行时只读它）")
    draft_graph = Column(JSON, nullable=False, default=dict, comment="草稿图配置（编辑器读写）")
    is_debug_passed = Column(
        Boolean, nullable=False, default=False, server_default=text("0"),
        comment="调试是否通过（发布闸门；改草稿即重置）",
    )
    status = Column(
        String(32), nullable=False, default="draft", server_default=text("('draft')"),
        comment="draft / published",
    )
    published_at = Column(DateTime, nullable=True, comment="发布时间")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkflowResult(db.Model):
    """工作流运行结果（追加型流水账）。当前仅调试页写入行。"""

    __tablename__ = "ai_workflow_result"
    __table_args__ = (
        Index("ix_ai_workflow_result_user_id", "user_id"),
        Index("ix_ai_workflow_result_app_id", "app_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id = Column(Integer, nullable=True, comment="预留：应用内调用的来源应用 id（现阶段只有调试页写行，恒为 NULL）")
    user_id = Column(Integer, nullable=False, comment="触发者账号 id（= account.id）")
    workflow_id = Column(
        Integer,
        ForeignKey("ai_workflow.id", name="fk_ai_workflow_result_workflow", ondelete="CASCADE"),
        nullable=False, comment="关联工作流 id",
    )
    graph = Column(JSON, nullable=False, default=dict, comment="运行时图快照（工作流后续改/删不影响历史回放）")
    state = Column(JSON, nullable=False, default=list, comment="全部节点的 NodeResult 列表")
    latency = Column(Float, nullable=False, default=0, server_default=text("0"), comment="总耗时（秒）")
    status = Column(
        String(32), nullable=False, default="running", server_default=text("('running')"),
        comment="running / succeeded / failed",
    )

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
