"""知识库（RAG）相关枚举与默认值。

- 文档/片段处理是异步多阶段流程，`*Status` 记录每一步的进度（前端轮询 batch 状态据此渲染）。
- `DEFAULT_PROCESS_RULE` 是 automatic 模式下的默认切分规则；custom 模式由前端覆盖 rule。
"""
from enum import Enum


class RetrievalStrategy(str, Enum):
    """检索策略。"""

    FULL_TEXT = "full_text"   # 全文（关键词倒排表）检索，得分恒 0
    SEMANTIC = "semantic"     # 语义（向量相似度）检索
    HYBRID = "hybrid"         # 混合（语义 + 全文，EnsembleRetriever 加权）


class RetrievalSource(str, Enum):
    """检索来源（写入 ai_dataset_query.source，用于统计区分）。"""

    HIT_TESTING = "hit_testing"  # 命中测试（控制台手动检索）
    APP = "app"                  # 应用对话内由 agent 调用（按-app chat 绑定知识库时触发）


class ProcessType(str, Enum):
    """文档处理模式。"""

    AUTOMATIC = "automatic"  # 用内置默认规则
    CUSTOM = "custom"        # 前端自定义 rule


class DocumentStatus(str, Enum):
    """文档索引状态机：waiting → parsing → splitting → indexing → completed（出错置 error）。"""

    WAITING = "waiting"
    PARSING = "parsing"
    SPLITTING = "splitting"
    INDEXING = "indexing"
    COMPLETED = "completed"
    ERROR = "error"


class SegmentStatus(str, Enum):
    """片段索引状态机：waiting → indexing → completed（出错置 error）。"""

    WAITING = "waiting"
    INDEXING = "indexing"
    COMPLETED = "completed"
    ERROR = "error"


# 单条片段的关键词上限（jieba TF-IDF 抽取）
DEFAULT_MAX_KEYWORD_PER_CHUNK = 10

# 命中测试默认参数
DEFAULT_RETRIEVAL_K = 4
DEFAULT_RETRIEVAL_SCORE = 0.0

# automatic 模式默认处理规则。
DEFAULT_PROCESS_RULE = {
    "mode": ProcessType.CUSTOM.value,
    "rule": {
        # 预处理：清洗多余空白 / URL / 邮箱
        "pre_process_rules": [
            {"id": "remove_extra_space", "enabled": True},
            {"id": "remove_url_and_email", "enabled": True},
        ],
        # 递归字符切分参数
        "segment": {
            "separators": [
                "\n\n", "\n",
                "。|！|？",
                r"\.\s|\!\s|\?\s",
                "；|;\\s",
                "，|,\\s",
                " ", "",
            ],
            "chunk_size": 500,
            "chunk_overlap": 50,
        },
    },
}
