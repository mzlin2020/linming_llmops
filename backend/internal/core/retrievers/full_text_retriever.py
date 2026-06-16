"""全文检索器（关键词倒排表）。

不走向量：jieba 分词 query → 在 ai_keyword_table 里查包含这些词的 segment_id → Counter 取 top-k →
回表 ai_segment 组装 LCDocument（score 恒 0）。倒排表里只会有"已启用"片段（启停时同步增删），
所以这里无需再过滤 enabled。

自包含（core → model + db，与 tool_resolver 同款），不反向 import service 层，避免循环依赖。
"""
from collections import Counter
from typing import Any, List

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document as LCDocument
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict

from internal.extension.database_extension import db
from internal.model import KeywordTable, Segment


def tokenize_keywords(query: str, topk: int = 10) -> List[str]:
    """用 jieba TF-IDF 抽取 query 关键词；jieba 不可用时退化为按空白/标点粗分。"""
    try:
        import jieba.analyse
        words = jieba.analyse.extract_tags(query or "", topK=topk)
        if words:
            return list(words)
    except Exception:
        pass
    # 退化：按非中英文数字切分
    import re
    return [w for w in re.split(r"[^\w一-鿿]+", query or "") if w][:topk]


class FullTextRetriever(BaseRetriever):
    """全文检索器（关键词命中频次排序）。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    dataset_ids: List[int]
    k: int = 4

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun,
    ) -> List[LCDocument]:
        keywords = tokenize_keywords(query)
        if not keywords:
            return []

        # 1. 合并这些知识库的关键词倒排表
        tables = db.session.query(KeywordTable).filter(
            KeywordTable.dataset_id.in_(self.dataset_ids)
        ).all()
        merged: dict = {}
        for t in tables:
            for kw, seg_ids in (t.keyword_table or {}).items():
                merged.setdefault(kw, set()).update(seg_ids or [])

        # 2. 命中关键词的 segment_id 计数
        counter: Counter = Counter()
        for kw in keywords:
            for seg_id in merged.get(kw, ()):  # type: ignore[arg-type]
                counter[seg_id] += 1
        if not counter:
            return []

        top_ids = [seg_id for seg_id, _ in counter.most_common(self.k)]

        # 3. 回表组装（按命中频次顺序）
        rows = db.session.query(Segment).filter(Segment.id.in_(top_ids)).all()
        by_id = {r.id: r for r in rows}
        documents: List[LCDocument] = []
        for seg_id in top_ids:
            seg = by_id.get(seg_id)
            if seg is None:
                continue
            documents.append(LCDocument(
                page_content=seg.content or "",
                metadata={
                    "dataset_id": seg.dataset_id,
                    "document_id": seg.document_id,
                    "segment_id": seg.id,
                    "node_id": seg.node_id,
                    "score": 0.0,
                },
            ))
        return documents
