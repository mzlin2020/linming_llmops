"""EmbeddingsManager：知识库向量化入口。

本地开源 embedding（默认 BAAI/bge-small-zh-v1.5，512 维），用 langchain-huggingface 的
HuggingFaceEmbeddings（底层 sentence-transformers）加载。

设计要点：
- **全局单例**：真正的模型对象用模块级 @lru_cache 缓存（对齐 vector_store/qdrant_vector_store.py 的
  get_qdrant_client 写法），无论 DI 造了几个 EmbeddingsManager 实例都共用一份模型，避免在同一进程内重复占内存
  （bge-small 单进程常驻约 200MB；注意 gunicorn/celery 每个 worker 各占一份，换大模型时按 worker 数累加）。
- **延迟导入**：torch / sentence-transformers 只在首次真正取 embeddings 时 import，导入本模块本身零重型依赖，
  方便无 GPU 的单测用 fake 替身（monkeypatch EmbeddingsManager.embeddings）。
- **query/document 不对称**：检索类 embedding 通常 query 侧加指令前缀、文档侧不加。
  bge-zh 系列用一段中文指令前缀（env EMBEDDING_QUERY_INSTRUCTION）；Qwen3 等用预置 prompt 名（env EMBEDDING_QUERY_PROMPT_NAME）。
  通过 HuggingFaceEmbeddings 的 query_encode_kwargs / encode_kwargs 区分 embed_query / embed_documents。
- 向量做归一化以配合 Qdrant 的 COSINE 距离（query/document 两侧都归一化）。
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Optional

# bge-zh-v1.5 官方推荐的检索 query 指令前缀（文档侧不加）；换模型可用 env EMBEDDING_QUERY_INSTRUCTION 覆盖/置空。
_DEFAULT_BGE_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："


def _env(key: str, default: str = "") -> str:
    val = os.getenv(key)
    return val if val not in (None, "") else default


@lru_cache(maxsize=1)
def _get_embeddings_singleton() -> Any:
    """构建并缓存全局唯一的 HuggingFaceEmbeddings。首次调用会触发模型权重加载/下载。"""
    from langchain_huggingface import HuggingFaceEmbeddings

    model_name = _env("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    device = _env("EMBEDDING_DEVICE", "cpu")
    normalize = _env("EMBEDDING_NORMALIZE", "True").lower() == "true"
    # 二选一（query_instruction 优先）：
    #   query_instruction —— 文字前缀，bge-zh 等用；置空字符串可关闭。
    #   prompt_name       —— sentence-transformers 预置 prompt 名，Qwen3 等用。
    query_instruction = _env("EMBEDDING_QUERY_INSTRUCTION", _DEFAULT_BGE_QUERY_INSTRUCTION)
    prompt_name = _env("EMBEDDING_QUERY_PROMPT_NAME", "") or None

    encode_kwargs = {"normalize_embeddings": normalize}
    query_encode_kwargs = dict(encode_kwargs)  # query 侧同样归一化
    if query_instruction:
        query_encode_kwargs["prompt"] = query_instruction
    elif prompt_name:
        query_encode_kwargs["prompt_name"] = prompt_name

    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": device},
        encode_kwargs=encode_kwargs,
        query_encode_kwargs=query_encode_kwargs,
    )


@lru_cache(maxsize=1)
def _get_tiktoken_encoder() -> Optional[Any]:
    try:
        import tiktoken
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


class EmbeddingsManager:
    """无外部依赖，DI 容器用 ClassProvider 自动构造（同 LanguageModelManager）。"""

    @property
    def vector_size(self) -> int:
        """Qdrant collection 的向量维 = 当前 embedding 模型输出维（唯一真相）。换模型必须同步改它并重建 collection。"""
        try:
            return int(_env("EMBEDDING_VECTOR_SIZE", "512"))
        except (TypeError, ValueError):
            return 512

    @property
    def embeddings(self) -> Any:
        """全局唯一的 LangChain Embeddings 实例（含 embed_documents / embed_query）。"""
        return _get_embeddings_singleton()

    @staticmethod
    def calculate_token_count(text: str) -> int:
        """tiktoken cl100k_base 估算 token 数（仅用于统计）；不可用时退化为字符数。"""
        enc = _get_tiktoken_encoder()
        if enc is None:
            return len(text or "")
        try:
            return len(enc.encode(text or ""))
        except Exception:
            return len(text or "")
