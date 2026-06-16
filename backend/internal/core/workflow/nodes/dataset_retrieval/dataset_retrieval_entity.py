"""知识库检索节点数据实体。"""
from pydantic import BaseModel, Field, field_validator

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity, VariableType, VariableValueType
from internal.entity.dataset_entity import DEFAULT_RETRIEVAL_K, DEFAULT_RETRIEVAL_SCORE, RetrievalStrategy
from internal.exception import ValidateErrorException

# 单个检索节点可关联的知识库数量上限（service 宽松校验与此处实体校验同源）
MAX_DATASETS_PER_NODE = 5


class RetrievalConfig(BaseModel):
    """检索配置。"""

    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.SEMANTIC
    k: int = DEFAULT_RETRIEVAL_K
    score: float = DEFAULT_RETRIEVAL_SCORE


class DatasetRetrievalNodeData(BaseNodeData):
    """知识库检索节点数据（dataset_ids 是本项目的 int 主键）。"""

    dataset_ids: list[int] = Field(default_factory=list)
    retrieval_config: RetrievalConfig = Field(default_factory=RetrievalConfig)
    inputs: list[VariableEntity] = Field(default_factory=list)
    outputs: list[VariableEntity] = Field(
        default_factory=lambda: [
            VariableEntity(name="combine_documents", value={"type": VariableValueType.GENERATED})
        ]
    )

    @field_validator("dataset_ids")
    @classmethod
    def validate_dataset_ids(cls, dataset_ids: list[int]) -> list[int]:
        """超出上限的部分截断（与 service 宽松校验的行为一致，保存流不报错）。"""
        return dataset_ids[:MAX_DATASETS_PER_NODE]

    @field_validator("outputs", mode="before")
    @classmethod
    def validate_outputs(cls, outputs):
        return [VariableEntity(name="combine_documents", value={"type": VariableValueType.GENERATED})]

    @field_validator("inputs")
    @classmethod
    def validate_inputs(cls, inputs: list[VariableEntity]) -> list[VariableEntity]:
        """输入必须恰好一个必填的 query:string。"""
        if len(inputs) != 1:
            raise ValidateErrorException(message="知识库节点输入变量信息出错")

        query_input = inputs[0]
        if query_input.name != "query" or query_input.type != VariableType.STRING or query_input.required is False:
            raise ValidateErrorException(message="知识库节点输入变量名字/变量类型/必填属性出错")

        return inputs
