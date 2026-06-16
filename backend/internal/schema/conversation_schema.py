"""会话 / 消息相关请求 + 出参 schema。

PaginatorReq 为共享分页基类（知识库文档/片段分页也复用，见 segment_service）；
其余为 Phase 4b（App + 对话）随 conversation handler 补齐的会话/消息 schema。
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PaginatorReq(BaseModel):
    current_page: int = Field(default=1, ge=1, le=9999)
    page_size: int = Field(default=20, ge=1, le=50)


class PageModel(BaseModel):
    list: list
    paginator: dict   # {current_page, page_size, total_page, total_record}


class ConversationItem(BaseModel):
    id: int
    app_id: int
    user_id: int
    title: str
    summary: Optional[str] = None
    is_pinned: bool = False
    invoke_from: str = "web_app"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class MessageItem(BaseModel):
    """会话消息分页出参：一条 = 一轮（query + answer）。"""
    id: int
    conversation_id: int
    app_id: int
    query: str = ""
    answer: str = ""
    image_urls: list[str] = Field(default_factory=list)
    file_infos: list[dict] = Field(default_factory=list, description="文档附件元数据 [{url,name,extension}]")
    status: str = "normal"
    error: str = ""
    provider: Optional[str] = None
    model_name: Optional[str] = None
    latency: float = 0.0
    total_token_count: int = 0
    total_price: float = 0.0
    agent_thoughts: list = Field(default_factory=list, description="本轮恒空，预留给后续 Agent 接入")
    created_at: Optional[datetime] = None

    # protected_namespaces=()：规避 pydantic v2 对 model_ 前缀字段的 namespace 警告
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class ConversationListReq(BaseModel):
    app_id: Optional[int] = Field(default=None, gt=0, description="筛选某个 app 下的会话")
    limit: int = Field(default=50, ge=1, le=200)


class ConversationRenameReq(BaseModel):
    """/conversations/<id>/name 端点：字段名为 name。"""
    name: str = Field(..., min_length=1, max_length=128)


class ConversationIsPinnedReq(BaseModel):
    is_pinned: bool


class GetMessagesWithPageReq(PaginatorReq):
    created_at: int = Field(
        default=0, ge=0,
        description="游标（时间戳秒）：返回 created_at < 此值的消息；0 表示从最新开始",
    )
