"""知识库 embedding 子系统：本地开源模型向量化入口。"""
from .embeddings_manager import EmbeddingsManager, warmup_embeddings

__all__ = ["EmbeddingsManager", "warmup_embeddings"]
