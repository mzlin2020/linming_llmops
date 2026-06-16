from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from internal.schema.conversation_schema import PaginatorReq


# pydantic v2 中 `model_config` 是 BaseModel 的类配置属性，不能作为字段名。
# 我们用 `model_config_payload` 字段 + alias="model_config" 既避开冲突，又对外保持原字段名。
# `protected_namespaces=()` 关掉 `model_` 前缀字段的 namespace 警告。
_PYD_CONFIG = ConfigDict(
    from_attributes=True,
    populate_by_name=True,
    protected_namespaces=(),
)


class AppCreateReq(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="应用名称")
    description: Optional[str] = Field(default="", max_length=512)
    icon: Optional[str] = Field(default="", max_length=512)
    preset_prompt: Optional[str] = Field(default=None, max_length=8000, description="系统提示词 / AI 人设")


class AppUpdateReq(BaseModel):
    """基础信息更新；附带的 preset/model/dialog 会桥接进草稿配置行（兼容旧端点）。"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    description: Optional[str] = Field(default=None, max_length=512)
    icon: Optional[str] = Field(default=None, max_length=512)
    preset_prompt: Optional[str] = Field(default=None, max_length=8000)
    model_config_payload: Optional[dict] = Field(default=None, alias="model_config",
                                                 description="{provider, model, parameters}")
    dialog_round: Optional[int] = Field(default=None, ge=0, le=100)

    model_config = _PYD_CONFIG


class AppItem(BaseModel):
    """应用基础信息出参。三表拆分后配置字段（preset/model/dialog）由 handler 从草稿行合并进响应。
    user_id 对全局内置 app 为 None。"""
    id: int
    user_id: Optional[int] = None
    name: str
    description: str = ""
    icon: str = ""
    status: str = "draft"
    is_default: bool = False
    is_assistant_agent: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = _PYD_CONFIG


class AppConfigItem(BaseModel):
    """配置全集（14 字段）。GET /apps/<id> 详情里嵌套此块（取自草稿行），
    /draft-app-config 与 /published-config 也复用同形结构。"""
    model_config_payload: dict = Field(default_factory=dict, alias="model_config")
    dialog_round: int = 3
    preset_prompt: str = ""
    tools: list = Field(default_factory=list)
    workflows: list = Field(default_factory=list)
    datasets: list = Field(default_factory=list)
    retrieval_config: dict = Field(default_factory=dict)
    long_term_memory: dict = Field(default_factory=lambda: {"enable": False})
    opening_statement: str = ""
    opening_questions: list = Field(default_factory=list)
    speech_to_text: dict = Field(default_factory=lambda: {"enable": False})
    text_to_speech: dict = Field(default_factory=lambda: {"enable": False})
    suggested_after_answer: dict = Field(default_factory=lambda: {"enable": True})
    review_config: dict = Field(default_factory=dict)

    model_config = _PYD_CONFIG


class GetAppStoreWithPageReq(PaginatorReq):
    """公共应用商店分页列表（current_page / page_size 继承自 PaginatorReq）。"""
    search_word: Optional[str] = Field(default=None, description="按应用名模糊搜索")


class FallbackHistoryReq(BaseModel):
    """回退历史版本到草稿。"""
    app_config_version_id: int = Field(..., gt=0, description="要回退的 published 历史版本行 id")


class PublishAppReq(BaseModel):
    """上架 / 下架公共应用商店（任意登录用户对自己已发布的应用，上架与下架共用一个端点）。"""
    is_public: bool = Field(..., description="True=上架到商店，False=从商店下架")


class DebugConversationSummaryReq(BaseModel):
    summary: str = Field(default="", max_length=8000)
