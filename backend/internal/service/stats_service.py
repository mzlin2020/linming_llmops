"""StatsService：全站公开统计（首页右侧栏「平台状态」卡）。

只读聚合：商店应用/插件数、内置工具数、知识库数、生成图片数、工作流数。
端点公开（游客可见），且首页每次渲染都会打——必须经 redis 缓存（5min）护住 MySQL；
redis 读写均 fail-open（故障时直算返回，公开端点不能因缓存层 500）。
"""
import json
from dataclasses import dataclass

from injector import inject

from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.extension.database_extension import db
from internal.extension.redis_extension import redis_client
from internal.model import AiImage, Dataset, PublicApp, PublicPlugin, Workflow

_CACHE_KEY = "ai:stats:site:v2"
_CACHE_TTL = 300


@inject
@dataclass
class StatsService:
    builtin_provider_manager: BuiltinProviderManager

    def get_site_stats(self) -> dict:
        """全站统计：先读缓存，miss 则现算并回写。"""
        try:
            cached = redis_client.get(_CACHE_KEY)
            if cached:
                return json.loads(cached)
        except Exception:
            pass  # redis 不可用：直接现算
        stats = self._compute_stats()
        try:
            redis_client.set(_CACHE_KEY, json.dumps(stats), ex=_CACHE_TTL)
        except Exception:
            pass  # 缓存写失败不影响返回
        return stats

    def _compute_stats(self) -> dict:
        def count(model) -> int:
            return int(db.session.query(db.func.count(model.id)).scalar() or 0)

        return {
            "app_count": count(PublicApp),
            "plugin_count": count(PublicPlugin),
            "builtin_tool_count": sum(
                len(provider.get_tool_entities())
                for provider in self.builtin_provider_manager.get_providers()
            ),
            "dataset_count": count(Dataset),
            "image_count": count(AiImage),
            "workflow_count": count(Workflow),
        }
