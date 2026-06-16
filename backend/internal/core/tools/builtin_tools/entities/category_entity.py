"""分类实体，映射 categories.yaml。"""
from pydantic import BaseModel, field_validator

from internal.exception import FailException


class CategoryEntity(BaseModel):
    """工具分类。icon 必须是 categories/icons/ 下的 .svg 文件名。"""

    category: str
    name: str
    icon: str

    @field_validator("icon")
    @classmethod
    def check_icon_extension(cls, value: str) -> str:
        if not value.endswith(".svg"):
            raise FailException(message=f"分类 icon 必须是 .svg 格式: {value}")
        return value
