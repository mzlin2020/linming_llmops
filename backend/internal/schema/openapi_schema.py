"""开放 API（service_api）聊天请求 schema（pydantic v2）。

刻意**不含任何历史轮数字段**——单次对话回溯多少轮由服务端变量 OPENAPI_HISTORY_MAX_TURNS 决定，
调用方无法覆盖（防外部塞大轮数把 token 成本打爆）。
"""
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class OpenAPIAppInfoReq(BaseModel):
    """开放 API 应用元信息查询参数（GET query string）。"""
    app_id: int = Field(..., gt=0, description="目标已发布应用 id")


class OpenAPIChatReq(BaseModel):
    """开放 API 聊天请求体。"""
    app_id: int = Field(..., gt=0, description="目标已发布应用 id")
    end_user_id: Optional[int] = Field(default=None, gt=0, description="终端用户 id；缺省则自动新建匿名终端用户")
    conversation_id: Optional[int] = Field(default=None, gt=0, description="会话 id；缺省则新建会话")
    query: str = Field(..., min_length=1, max_length=8000, description="用户提问")
    # 数量上限由 service 层按 CHAT_MAX_*_PER_MESSAGE 配置校验（env 可调），schema 不另写一份
    image_urls: list[str] = Field(
        default_factory=list,
        description="图片附件 URL（存储白名单域）；要求应用配置的模型带 vision",
    )
    file_urls: list[str] = Field(
        default_factory=list,
        description="文档附件 URL（txt/md/csv/docx/xlsx/pdf），文本抽取后注入 LLM，任何模型可用",
    )
    stream: bool = Field(default=True, description="True=SSE 流式；False=一次性返回完整回答")

    @model_validator(mode="after")
    def _conversation_requires_end_user(self):
        # 复用已有会话必须指明终端用户，否则无法校验归属
        if self.conversation_id is not None and self.end_user_id is None:
            raise ValueError("传递会话 id 时终端用户 id 不能为空")
        return self
