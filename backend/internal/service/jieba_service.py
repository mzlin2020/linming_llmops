"""JiebaService：中文关键词抽取（TF-IDF），用于文档索引时给片段打关键词。

jieba 延迟 import：缺包不影响模块导入，仅退化为空关键词（全文检索召回降级，语义检索不受影响）。
"""
from dataclasses import dataclass
from typing import List

from injector import inject


@inject
@dataclass
class JiebaService:
    def extract_keywords(self, text: str, max_keyword_per_chunk: int = 10) -> List[str]:
        if not text:
            return []
        try:
            import jieba.analyse
            return list(jieba.analyse.extract_tags(text, topK=max_keyword_per_chunk))
        except Exception:
            return []
