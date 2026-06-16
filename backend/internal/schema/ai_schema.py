from pydantic import BaseModel, Field


class OptimizePromptReq(BaseModel):
    """优化人设提示词。"""
    prompt: str = Field(..., min_length=1, max_length=8000, description="待优化的人设提示词")


class SuggestOpeningQuestionsReq(BaseModel):
    """根据人设生成开场建议问题。prompt 允许为空（生成通用问题）。"""
    prompt: str = Field(default="", max_length=8000, description="应用人设，可空")


class SuggestQuestionsReq(BaseModel):
    """根据某条消息（一轮问答）生成 follow-up 建议问题。"""
    message_id: int = Field(..., gt=0, description="据以生成 follow-up 的消息行 id")
