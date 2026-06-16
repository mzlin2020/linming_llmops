"""KeywordTableService：维护知识库的关键词倒排表 ai_keyword_table（供全文检索）。

一个 dataset 一行 {keyword: [segment_id,...]}。增删都在 redis 锁内做"读快照→改→写回"，避免并发丢更新。
倒排表里只放"已启用"片段——启用/禁用片段或文档时由 indexing/segment service 调本服务同步增删。
"""
from dataclasses import dataclass
from typing import List

from injector import inject

from internal.extension.database_extension import db
from internal.extension.redis_extension import redis_client
from internal.model import KeywordTable, Segment

_LOCK_PREFIX = "lock:keyword_table:"
_LOCK_TTL = 600


@inject
@dataclass
class KeywordTableService:
    def get_or_create(self, dataset_id: int) -> KeywordTable:
        row = db.session.query(KeywordTable).filter(KeywordTable.dataset_id == dataset_id).one_or_none()
        if row is None:
            row = KeywordTable(dataset_id=dataset_id, keyword_table={})
            with db.auto_commit():
                db.session.add(row)
            db.session.refresh(row)
        return row

    def add_keyword_table_from_ids(self, dataset_id: int, segment_ids: List[int]) -> None:
        if not segment_ids:
            return
        with redis_client.lock(f"{_LOCK_PREFIX}{dataset_id}", timeout=_LOCK_TTL):
            kt = self.get_or_create(dataset_id)
            table = dict(kt.keyword_table or {})
            segments = db.session.query(Segment).filter(Segment.id.in_(segment_ids)).all()
            for seg in segments:
                for kw in (seg.keywords or []):
                    ids = set(table.get(kw, []))
                    ids.add(seg.id)
                    table[kw] = sorted(ids)
            with db.auto_commit():
                kt.keyword_table = table

    def delete_keyword_table_from_ids(self, dataset_id: int, segment_ids: List[int]) -> None:
        if not segment_ids:
            return
        remove = {int(i) for i in segment_ids}
        with redis_client.lock(f"{_LOCK_PREFIX}{dataset_id}", timeout=_LOCK_TTL):
            kt = self.get_or_create(dataset_id)
            table = dict(kt.keyword_table or {})
            new_table = {}
            for kw, ids in table.items():
                remaining = [i for i in (ids or []) if int(i) not in remove]
                if remaining:
                    new_table[kw] = remaining
            with db.auto_commit():
                kt.keyword_table = new_table
