"""API 工具实体：记录创建 LangChain 工具所需的配置。"""
from pydantic import BaseModel, Field


class ToolEntity(BaseModel):
    """API 工具实体信息。id 取自 ai_api_tool 行（构造时传 str(row.id)），用于生成工具名。"""
    id: str = Field(default="", description="API 工具对应的 id")
    name: str = Field(default="", description="API 工具的名称（operationId）")
    url: str = Field(default="", description="API 工具发起请求的 URL 地址")
    method: str = Field(default="get", description="API 工具发起请求的方法")
    description: str = Field(default="", description="API 工具的描述信息")
    headers: list[dict] = Field(default_factory=list, description="API 工具的请求头信息")
    parameters: list[dict] = Field(default_factory=list, description="API 工具的参数列表信息")
