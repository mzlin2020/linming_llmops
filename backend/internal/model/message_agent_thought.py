"""自有表：ai_message_agent_thought。

记录单条 ai_message 在 Agent 推理时的中间步骤（思考 / 工具调用 / 观察）。
本轮仅建表，不读不写。未来接入 AgentQueueManager + FunctionCallAgent 时启用。
所有字段都 NOT NULL + server_default，避免插入时漏字段。
"""
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    text,
)

from internal.extension.database_extension import db


class MessageAgentThought(db.Model):
    __tablename__ = "ai_message_agent_thought"
    __table_args__ = (
        Index("ix_ai_message_agent_thought_message_id", "message_id"),
        Index("ix_ai_message_agent_thought_conversation_id", "conversation_id"),
        Index("ix_ai_message_agent_thought_app_id", "app_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id = Column(
        Integer,
        ForeignKey("ai_app.id", ondelete="CASCADE", name="fk_ai_message_agent_thought_app"),
        nullable=False,
    )
    conversation_id = Column(
        Integer,
        ForeignKey("ai_conversation.id", ondelete="CASCADE", name="fk_ai_message_agent_thought_conversation"),
        nullable=False,
    )
    message_id = Column(
        Integer,
        ForeignKey("ai_message.id", ondelete="CASCADE", name="fk_ai_message_agent_thought_message"),
        nullable=False,
    )
    invoke_from = Column(String(32), nullable=False, default="web_app", server_default="web_app")
    created_by = Column(Integer, nullable=False, default=0, server_default=text("0"), comment="创建者账号 id（软引用）")

    position = Column(Integer, nullable=False, default=0, server_default=text("0"), comment="步骤序号")
    event = Column(String(32), nullable=False, default="", server_default="", comment="对齐 QueueEvent 名")
    thought = Column(Text, nullable=False, default="", server_default="", comment="LLM 思考")
    observation = Column(Text, nullable=False, default="", server_default="", comment="工具/RAG 输出")
    tool = Column(Text, nullable=False, default="", server_default="", comment="工具名")
    tool_input = Column(JSON, nullable=False, default=dict, server_default=text("('{}')"), comment="工具入参")
    message = Column(JSON, nullable=False, default=list, server_default=text("('[]')"), comment="该步骤 prompt")

    message_token_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    message_unit_price = Column(Numeric(10, 7), nullable=False, default=0, server_default=text("0"))
    message_price_unit = Column(Numeric(10, 4), nullable=False, default=0, server_default=text("0"))
    answer = Column(Text, nullable=False, default="", server_default="")
    answer_token_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    answer_unit_price = Column(Numeric(10, 7), nullable=False, default=0, server_default=text("0"))
    answer_price_unit = Column(Numeric(10, 4), nullable=False, default=0, server_default=text("0"))
    total_token_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    total_price = Column(Numeric(10, 7), nullable=False, default=0, server_default=text("0"))
    latency = Column(Float, nullable=False, default=0.0, server_default=text("0"))

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
