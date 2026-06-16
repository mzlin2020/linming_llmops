from typing import Optional

from pydantic import BaseModel, Field


class DebugChatReq(BaseModel):
    """debug_chat 请求形状。conversation_id 为空时走该 app 的「默认会话」，无则建；
    不为空时附加到指定会话，需归属当前用户且属于该 app。"""
    query: str = Field(..., min_length=1, max_length=8000, description="用户提问")
    # 数量上限由 service 层按 CHAT_MAX_*_PER_MESSAGE 配置校验（env 可调），schema 不另写一份
    image_urls: list[str] = Field(
        default_factory=list,
        description="图片附件 URL（白名单域）；要求所选模型带 vision",
    )
    file_urls: list[str] = Field(
        default_factory=list,
        description="文档附件 URL（txt/md/csv/docx/xlsx/pdf），文本抽取后注入 LLM，任何模型可用",
    )
    conversation_id: Optional[int] = Field(default=None, gt=0)
