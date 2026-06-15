"""自有表：ai_api_tool_provider / ai_api_tool（自定义 API 工具 / 插件）+ ai_public_plugin（公共插件商店）。

结构：
- ai_api_tool_provider —— 一份 OpenAPI schema = 一个工具提供者（name + icon + openapi_schema + 公共 headers）
- ai_api_tool          —— schema 里的一个 operation（一条可调用工具：url + method + parameters）
- ai_public_plugin     —— 公共插件商店：把自己的私有插件「发布」成的自包含快照，全员可读、可一键复制

按 user_id 归属隔离：每个登录账号只能管理自己的插件。provider 删除时其下 tool 经 FK CASCADE 连带删除。
公共商店与私有表通过「复制快照」解耦：发布=把私有 provider 字段复制进 ai_public_plugin；
添加=把公共条目复制回私有表（私有 provider.source_public_id 记录来源，用于商店「是否已添加」去重）。
user_id / published_by 是普通索引列（= account.id），不加 FK。
"""
from datetime import datetime

from sqlalchemy import (
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


class ApiToolProvider(db.Model):
    """自定义 API 工具提供者：一份 OpenAPI schema + 公共请求头。"""

    __tablename__ = "ai_api_tool_provider"
    __table_args__ = (
        Index("ix_ai_api_tool_provider_user_id", "user_id"),
        Index("ix_ai_api_tool_provider_user_id_name", "user_id", "name"),
        Index("ix_ai_api_tool_provider_source_public_id", "source_public_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, nullable=False, comment="归属账号 id（= account.id）",
    )
    name = Column(String(64), nullable=False, default="", server_default="", comment="工具提供者名（同用户内唯一）")
    icon = Column(String(512), nullable=False, default="", server_default="", comment="图标 URL")
    description = Column(Text, nullable=False, default="", server_default="", comment="提供者描述（取自 openapi schema）")
    openapi_schema = Column(Text, nullable=False, default="", server_default="", comment="原始 OpenAPI schema JSON 字符串")
    headers = Column(JSON, nullable=False, default=list, server_default=text("('[]')"), comment="公共请求头 [{key,value}]")
    source_public_id = Column(
        Integer, nullable=True,
        comment="从哪条公共插件复制来（ai_public_plugin.id，软引用）；自建插件恒空。用于商店「是否已添加」去重",
    )

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    tools = relationship(
        "ApiTool", backref="provider",
        cascade="all, delete-orphan", passive_deletes=True,
    )


class ApiTool(db.Model):
    """自定义 API 工具：OpenAPI schema 里的一个 operation。"""

    __tablename__ = "ai_api_tool"
    __table_args__ = (
        Index("ix_ai_api_tool_user_id", "user_id"),
        Index("ix_ai_api_tool_provider_id_name", "provider_id", "name"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, nullable=False, comment="归属账号 id（= account.id）",
    )
    provider_id = Column(
        Integer,
        ForeignKey("ai_api_tool_provider.id", ondelete="CASCADE", name="fk_ai_api_tool_provider"),
        nullable=False, comment="所属 provider",
    )
    name = Column(String(128), nullable=False, default="", server_default="", comment="工具名（OpenAPI operationId）")
    description = Column(Text, nullable=False, default="", server_default="", comment="工具描述")
    url = Column(String(512), nullable=False, default="", server_default="", comment="请求 URL（server + path）")
    method = Column(String(16), nullable=False, default="get", server_default="get", comment="HTTP 方法 get/post")
    parameters = Column(JSON, nullable=False, default=list, server_default=text("('[]')"), comment="参数列表 [{name,in,description,required,type}]")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class PublicPlugin(db.Model):
    """公共插件商店条目：把私有 provider「发布」成的自包含快照。

    自包含 = 复制了 name/icon/description/openapi_schema/headers，并额外存一份 tools 展示快照，
    商店列表零解析即可渲染卡片；用户「添加」时再用 openapi_schema 走标准解析拆回私有 tool 行。
    source_provider_id 唯一：一条私有 provider 至多对应一条公共条目（便于发布 upsert / 取消发布 / 连带下架定位）。
    """

    __tablename__ = "ai_public_plugin"
    __table_args__ = (
        Index("uq_ai_public_plugin_source_provider_id", "source_provider_id", unique=True),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False, default="", server_default="", comment="插件名")
    icon = Column(String(512), nullable=False, default="", server_default="", comment="图标 URL")
    description = Column(Text, nullable=False, default="", server_default="", comment="插件描述")
    openapi_schema = Column(Text, nullable=False, default="", server_default="", comment="原始 OpenAPI schema（复制到私有用）")
    headers = Column(JSON, nullable=False, default=list, server_default=text("('[]')"), comment="公共请求头 [{key,value}]")
    tools = Column(JSON, nullable=False, default=list, server_default=text("('[]')"), comment="工具展示快照 [{name,description,inputs}]")
    category = Column(String(32), nullable=False, default="", server_default="", comment="分类（预留，先空）")
    sort = Column(Integer, nullable=False, default=0, server_default=text("0"), comment="排序权重，大在前")
    published_by = Column(
        Integer, nullable=False, comment="发布者账号 id（= account.id）",
    )
    source_provider_id = Column(Integer, nullable=False, comment="来源私有 provider id（软引用，无 FK）")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
