"""会话相关请求 schema。

本期（Phase 4a）仅落地共享的分页基类 PaginatorReq（知识库文档/片段分页复用）；
会话 / 消息的完整 schema 在 Phase 4b（App + 对话）随 conversation handler 一并补齐。
"""
from pydantic import BaseModel, Field


class PaginatorReq(BaseModel):
    current_page: int = Field(default=1, ge=1, le=9999)
    page_size: int = Field(default=20, ge=1, le=50)
