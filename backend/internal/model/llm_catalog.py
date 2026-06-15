"""自有表：AI 模型目录（DB 化，可在管理后台配置）。3 张表，全部 ai_ 前缀。

- ai_llm_provider —— 一个提供商 = 一组共享 protocol 的上游入口。单渠道模式自带 base_url + 加密 key；
  multi_channel=true（如第三方中转）则凭证下沉到 ai_llm_channel，按优先级兜底。
- ai_llm_model    —— 提供商下的一个模型卡（类型 / 能力 / 参数规则 / 计费等元数据，对齐 ModelEntity）。
- ai_llm_channel  —— 仅 multi_channel provider 用：一个模型可经多个中转渠道（base_url+key）兜底调用。
  渠道健康（连续失败 / 熔断）走 redis（热路径不写 DB），故本表**不存**健康列；后台展示也读 redis。

凭证（api_key_cipher / 渠道 api_key_cipher）以 Fernet 密文落库（加解密逻辑随 service 在后续阶段接入），
对外只读接口只序列化公开元数据、**永不返回密钥**。
旧提供商可由迁移种子导入：api_key_cipher 留空、api_key_env 指向 env 变量名，凭证读取回落 env。
本表无 user_id 列，模型目录全局共享。
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    text,
)
from sqlalchemy.orm import relationship

from internal.extension.database_extension import db


class LlmProvider(db.Model):
    """模型提供商。name 唯一（对齐目录名）。"""

    __tablename__ = "ai_llm_provider"
    __table_args__ = (
        Index("ix_ai_llm_provider_name", "name", unique=True),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False, default="", server_default="", comment="唯一标识，全小写下划线")
    label = Column(JSON, nullable=False, default=dict, server_default=text("('{}')"), comment="多语言展示名 {zh_Hans,en_US}")
    description = Column(JSON, nullable=False, default=dict, server_default=text("('{}')"), comment="多语言描述")
    icon = Column(String(512), nullable=False, default="", server_default="", comment="icon URL（新建）或旧目录文件名")
    background = Column(String(32), nullable=False, default="", server_default="", comment="UI 主色背景，可选")
    supported_model_types = Column(JSON, nullable=False, default=list, server_default=text("('[]')"), comment='["chat"/"text2img"/"tts"...]')
    protocol = Column(String(32), nullable=False, default="openai", server_default="openai", comment="须匹配协议注册表 key：openai/anthropic/volc_tts_ws")
    multi_channel = Column(Boolean, nullable=False, default=False, server_default=text("0"), comment="true=走渠道池兜底（如第三方中转）")
    base_url = Column(String(512), nullable=False, default="", server_default="", comment="单渠道模式的 base_url")
    api_key_cipher = Column(Text, nullable=False, default="", server_default="", comment="单渠道模式 API Key 的 Fernet 密文")
    api_key_env = Column(String(128), nullable=False, default="", server_default="", comment="旧 env 变量名兜底（密文为空时回落）")
    enabled = Column(Boolean, nullable=False, default=True, server_default=text("1"), comment="是否启用（禁用则运行期/公开列表都不出现）")
    sort = Column(Integer, nullable=False, default=0, server_default="0", comment="展示排序")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    models = relationship(
        "LlmModel", backref="provider",
        cascade="all, delete-orphan", passive_deletes=True,
        order_by="LlmModel.sort",
    )
    channels = relationship(
        "LlmChannel", backref="provider",
        cascade="all, delete-orphan", passive_deletes=True,
        order_by="LlmChannel.priority",
    )


class LlmModel(db.Model):
    """提供商下的一个模型卡。"""

    __tablename__ = "ai_llm_model"
    __table_args__ = (
        Index("ix_ai_llm_model_provider_id", "provider_id"),
        Index("ix_ai_llm_model_provider_model", "provider_id", "model_name", unique=True),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_id = Column(
        Integer,
        ForeignKey("ai_llm_provider.id", ondelete="CASCADE", name="fk_ai_llm_model_provider"),
        nullable=False, comment="所属提供商",
    )
    model_name = Column(String(128), nullable=False, default="", server_default="", comment="上游 SDK 的 model 参数")
    label = Column(JSON, nullable=False, default=dict, server_default=text("('{}')"), comment="多语言展示名")
    model_type = Column(String(32), nullable=False, default="chat", server_default="chat", comment="chat/text2img/tts/embedding...")
    features = Column(JSON, nullable=False, default=list, server_default=text("('[]')"), comment='["tool_call","vision","streaming"...]')
    context_window = Column(Integer, nullable=False, default=4096, server_default="4096", comment="上下文窗口")
    max_output_tokens = Column(Integer, nullable=True, comment="单次最大输出 tokens")
    parameter_rules = Column(JSON, nullable=False, default=list, server_default=text("('[]')"), comment="可调参数规则")
    pricing = Column(JSON, nullable=True, comment="{input,output,unit,currency}，可空")
    deprecated = Column(Boolean, nullable=False, default=False, server_default=text("0"), comment="是否弃用（列表里会过滤）")
    admin_only = Column(Boolean, nullable=False, default=False, server_default=text("0"), comment="仅特定权限可调（如文生图）")
    is_default = Column(Boolean, nullable=False, default=False, server_default=text("0"), comment="是否该类型默认模型（展示用）")
    enabled = Column(Boolean, nullable=False, default=True, server_default=text("1"), comment="是否启用")
    sort = Column(Integer, nullable=False, default=0, server_default="0", comment="展示排序")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class LlmChannel(db.Model):
    """兜底渠道（仅 multi_channel provider 用）：一个 base_url + 加密 key 的上游入口。

    健康状态（连续失败计数 / 熔断到期）不落库，全在 redis；本表只存渠道**配置**。
    models 白名单为空 = 支持该 provider 全部模型。
    """

    __tablename__ = "ai_llm_channel"
    __table_args__ = (
        Index("ix_ai_llm_channel_provider_priority", "provider_id", "priority"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_id = Column(
        Integer,
        ForeignKey("ai_llm_provider.id", ondelete="CASCADE", name="fk_ai_llm_channel_provider"),
        nullable=False, comment="所属提供商",
    )
    name = Column(String(128), nullable=False, default="", server_default="", comment="渠道备注名")
    base_url = Column(String(512), nullable=False, default="", server_default="", comment="该渠道 base_url")
    api_key_cipher = Column(Text, nullable=False, default="", server_default="", comment="该渠道 API Key 的 Fernet 密文")
    priority = Column(Integer, nullable=False, default=0, server_default="0", comment="越小越先试")
    models = Column(JSON, nullable=False, default=list, server_default=text("('[]')"), comment="支持的 model_name 白名单，空=全部")
    enabled = Column(Boolean, nullable=False, default=True, server_default=text("1"), comment="是否启用")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
