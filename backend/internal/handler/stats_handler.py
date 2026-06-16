"""StatsHandler：全站公开统计（只读）。

刻意不加 @RequireLogin —— 首页右侧栏游客也要能看（先例 GET /api/ping）；
纯读 count 聚合不触发 LLM，DB 压力由 service 层的 redis 5min 缓存兜住。
"""
from dataclasses import dataclass

from injector import inject

from internal.service import StatsService
from pkg.response import success


@inject
@dataclass
class StatsHandler:
    stats_service: StatsService

    def get_site_stats(self):
        """GET /api/stats —— 全站统计（公开）。"""
        return success(self.stats_service.get_site_stats())
