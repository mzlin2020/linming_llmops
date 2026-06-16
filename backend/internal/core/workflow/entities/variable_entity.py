"""工作流变量实体（pydantic v2）。

变量取值三种来源：literal（编辑器直接填）、ref（引用前驱节点的输出变量）、
generated（运行期生成，开始节点输入 / 各节点固定输出用）。
"""
import re
from enum import Enum
from typing import Any, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from internal.exception import ValidateErrorException


class VariableType(str, Enum):
    """变量的数据类型枚举。"""

    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOLEAN = "boolean"


# 变量类型与 Python 类型的映射
VARIABLE_TYPE_MAP = {
    VariableType.STRING: str,
    VariableType.INT: int,
    VariableType.FLOAT: float,
    VariableType.BOOLEAN: bool,
}

# 变量类型默认值映射
VARIABLE_TYPE_DEFAULT_VALUE_MAP = {
    VariableType.STRING: "",
    VariableType.INT: 0,
    VariableType.FLOAT: 0,
    VariableType.BOOLEAN: False,
}

# 变量名字正则匹配规则
VARIABLE_NAME_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"

# 描述最大长度
VARIABLE_DESCRIPTION_MAX_LENGTH = 1024


class VariableValueType(str, Enum):
    """变量取值来源枚举。"""

    REF = "ref"  # 引用前驱节点输出
    LITERAL = "literal"  # 字面量/直接输入
    GENERATED = "generated"  # 运行期生成（开始节点输入或节点固定输出）


class VariableEntity(BaseModel):
    """变量实体信息。"""

    class Value(BaseModel):
        """变量的值信息。"""

        class Content(BaseModel):
            """引用类型的内容：引用节点 id + 引用变量名。"""

            ref_node_id: Optional[UUID] = None
            ref_var_name: str = ""

            @field_validator("ref_node_id", mode="before")
            @classmethod
            def validate_ref_node_id(cls, ref_node_id: Any) -> Any:
                return ref_node_id if ref_node_id != "" else None

        type: VariableValueType = VariableValueType.LITERAL
        content: Union[Content, str, int, float, bool] = ""

    name: str = ""  # 变量名
    description: str = ""
    required: bool = True
    type: VariableType = VariableType.STRING
    value: Value = Field(default_factory=lambda: VariableEntity.Value())
    meta: dict[str, Any] = Field(default_factory=dict)  # 额外元数据（如 http_request 的 params/headers/body 归类）

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not re.match(VARIABLE_NAME_PATTERN, value):
            raise ValidateErrorException(message="变量名字仅支持字母、数字和下划线，且以字母/下划线为开头")
        return value

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return value[:VARIABLE_DESCRIPTION_MAX_LENGTH]
