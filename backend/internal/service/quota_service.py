"""QuotaService：知识库配额 / 限流（防滥用安全网，对所有登录用户统一生效）。

本平台无管理员概念（Account.is_admin 恒 False），故不再有「超管豁免」分支：所有登录用户走同一套
可配置配额。每个上限均支持「<=0 = 不限」哨兵，self-hosted 单机想完全放开时把对应 env 调成 0 即可。

约束维度：知识库数、单库文档数、单文件大小（DB/请求维度，可靠）；灌库冷却 + 日次数、命中每分钟/每天
（redis 计数维度，redis 不可用时 fail-open 放行）。阈值全部走 current_app.config（env 可调）。
redis key 统一 ai:quota: 前缀。
"""
from dataclasses import dataclass
from datetime import datetime

from flask import current_app
from injector import inject

from internal.exception import RateLimitException, ValidateErrorException
from internal.extension.database_extension import db
from internal.extension.redis_extension import redis_client
from internal.model import Account, Dataset, Document, Workflow

# 计数窗口的 TTL 余量：日窗口给 25h（覆盖跨自然日的边界，过期由新 key 自然滚动）
_DAY_TTL = 25 * 60 * 60
_MIN_TTL = 60


@inject
@dataclass
class QuotaService:
    """配额检查无需注入其它 service：只用 redis_client + db + current_app.config。"""

    # ---------- 配额 / 限流检查（对所有登录用户统一生效；阈值 <=0 表示不限） ----------

    def check_create_dataset(self, user: Account) -> None:
        limit = int(current_app.config.get("QUOTA_MAX_DATASETS_PER_USER", 3))
        if limit <= 0:
            return
        count = db.session.query(db.func.count(Dataset.id)).filter(
            Dataset.user_id == user.id
        ).scalar() or 0
        if count >= limit:
            raise ValidateErrorException(
                message=f"知识库数量已达上限（最多 {limit} 个），请删除后再建或联系管理员"
            )

    def check_create_workflow(self, user: Account) -> None:
        limit = int(current_app.config.get("QUOTA_MAX_WORKFLOWS_PER_USER", 3))
        if limit <= 0:
            return
        count = db.session.query(db.func.count(Workflow.id)).filter(
            Workflow.user_id == user.id
        ).scalar() or 0
        if count >= limit:
            raise ValidateErrorException(
                message=f"工作流数量已达上限（最多 {limit} 个），请删除后再建或联系管理员"
            )

    def check_workflow_debug(self, user: Account) -> None:
        """工作流调试限额：每天 N 次（调试会真实跑 LLM 节点/HTTP 请求）。redis 不可用时放行。"""
        per_day = int(current_app.config.get("QUOTA_WORKFLOW_DEBUG_DAILY_LIMIT", 20))
        if per_day <= 0:
            return
        self._incr_window(
            f"ai:quota:wf_debug:day:{user.id}:{datetime.utcnow().strftime('%Y%m%d')}", _DAY_TTL, per_day,
            f"今日工作流调试次数已达上限（每天 {per_day} 次），请明天再试或联系管理员",
        )

    def check_add_documents(self, user: Account, dataset_id: int, new_count: int) -> None:
        """建文档（灌库）：①单库文档数上限；②灌库预算（冷却 + 日次数）。"""
        limit = int(current_app.config.get("QUOTA_MAX_DOCS_PER_DATASET", 5))
        if limit > 0:
            existing = db.session.query(db.func.count(Document.id)).filter(
                Document.dataset_id == dataset_id
            ).scalar() or 0
            if existing + max(0, new_count) > limit:
                raise ValidateErrorException(
                    message=f"该知识库文档数将超过上限（每库最多 {limit} 篇），请精简后再传"
                )
        self._check_build_budget(user)

    def check_reindex(self, user: Account) -> None:
        self._check_build_budget(user)

    def max_upload_size(self, user: Account) -> int:
        """单文件大小上限：统一取 QUOTA_USER_UPLOAD_MAX_SIZE；<=0 时回落到全局 UPLOAD_MAX_SIZE。"""
        size = int(current_app.config.get("QUOTA_USER_UPLOAD_MAX_SIZE", 2097152))
        if size <= 0:
            return int(current_app.config.get("UPLOAD_MAX_SIZE", 15728640))
        return size

    def check_hit(self, user: Account) -> None:
        """命中检索限速：每分钟 + 每天。redis 不可用时放行。"""
        per_min = int(current_app.config.get("QUOTA_HIT_PER_MINUTE", 10))
        per_day = int(current_app.config.get("QUOTA_HIT_DAILY_LIMIT", 100))
        now = datetime.utcnow()
        if per_min > 0:
            self._incr_window(
                f"ai:quota:hit:min:{user.id}:{now.strftime('%Y%m%d%H%M')}", _MIN_TTL, per_min,
                "检索过于频繁，请稍后再试（每分钟上限已达）",
            )
        if per_day > 0:
            self._incr_window(
                f"ai:quota:hit:day:{user.id}:{now.strftime('%Y%m%d')}", _DAY_TTL, per_day,
                "今日检索次数已达上限，请明天再试或联系管理员",
            )

    def check_openapi_chat(self, user: Account) -> None:
        """开放 API 聊天限速：按账号（API key 归属人）每分钟 + 每天。

        redis 不可用时放行（fail-open）。对外接口故超限抛 429（RateLimitException）。
        """
        per_min = int(current_app.config.get("QUOTA_OPENAPI_PER_MINUTE", 10))
        per_day = int(current_app.config.get("QUOTA_OPENAPI_DAILY_LIMIT", 30))
        now = datetime.utcnow()
        if per_min > 0:
            self._incr_window(
                f"ai:quota:openapi:min:{user.id}:{now.strftime('%Y%m%d%H%M')}", _MIN_TTL, per_min,
                "调用过于频繁，请稍后再试（每分钟上限已达）", exc=RateLimitException,
            )
        if per_day > 0:
            self._incr_window(
                f"ai:quota:openapi:day:{user.id}:{now.strftime('%Y%m%d')}", _DAY_TTL, per_day,
                "今日 API 调用次数已达上限，请明天再试", exc=RateLimitException,
            )

    def check_image_generation(self, user: Account) -> None:
        """图像生成每日上限：纯成本安全网（防误触爆量花钱）。

        redis 不可用时放行（fail-open）；QUOTA_IMAGE_DAILY_LIMIT<=0 表示不限。"""
        per_day = int(current_app.config.get("QUOTA_IMAGE_DAILY_LIMIT", 100))
        if per_day <= 0:
            return
        now = datetime.utcnow()
        self._incr_window(
            f"ai:quota:image:day:{user.id}:{now.strftime('%Y%m%d')}", _DAY_TTL, per_day,
            f"今日图像生成次数已达上限（每天 {per_day} 张），请明天再试或调高 QUOTA_IMAGE_DAILY_LIMIT",
        )

    def check_chat_attachment(self, user: Account, count: int) -> None:
        """聊天附件配额：图片+文档合计 个/天（一个计数器）。

        在消息真正发出时（append_round 前）按本轮附件数一次 incrby 并校验阈值。
        redis 不可用时放行（fail-open）。"""
        per_day = int(current_app.config.get("QUOTA_CHAT_ATTACHMENTS_PER_DAY", 2))
        if count <= 0 or per_day <= 0:
            return
        key = f"ai:quota:chat_attach:day:{user.id}:{datetime.utcnow().strftime('%Y%m%d')}"
        try:
            n = int(redis_client.incrby(key, count))
            if n == count:  # 首次写入设 TTL
                redis_client.expire(key, _DAY_TTL)
        except Exception:
            return  # redis 不可用：放行，不阻断
        if n > per_day:
            raise ValidateErrorException(
                message=f"今日图片/文档附件数已达上限（每天 {per_day} 个），请明天再试或联系管理员"
            )

    def check_tts(self, user: Account, message_id: str) -> None:
        """文本转语音（TTS 实时播报）配额：每天 N 条不同回复（按 message_id 去重）。

        口径 = 「播一整条 AI 回复算 1 次」：同一条回复按句多次调合成，message_id 相同 → 只计 1 次。
        redis 不可用时放行（fail-open）。QUOTA_TTS_DAILY_LIMIT<=0 表示不限。
        """
        per_day = int(current_app.config.get("QUOTA_TTS_DAILY_LIMIT", 2))
        if per_day <= 0:
            return
        key = f"ai:quota:tts:day:{user.id}:{datetime.utcnow().strftime('%Y%m%d')}"
        mid = str(message_id or "")
        try:
            added = int(redis_client.sadd(key, mid))
            if added == 0:
                return  # 同一条回复的后续句子 → 免费
            size = int(redis_client.scard(key))
            if size == 1:
                redis_client.expire(key, _DAY_TTL)  # 仅首次设 25h TTL
            if size > per_day:
                redis_client.srem(key, mid)  # 回滚，避免被拒的 message_id 永久占坑
                raise ValidateErrorException(
                    message=f"今日语音播报次数已达上限（每天 {per_day} 次），请明天再试或联系管理员"
                )
        except ValidateErrorException:
            raise
        except Exception:
            return  # redis 不可用：放行，不阻断

    # ---------- 记账（在成功派发灌库 / 重索引之后调用） ----------

    def record_build(self, user: Account) -> None:
        cooldown = int(current_app.config.get("QUOTA_BUILD_COOLDOWN_SECONDS", 600))
        now = datetime.utcnow()
        try:
            day_key = f"ai:quota:build:day:{user.id}:{now.strftime('%Y%m%d')}"
            n = int(redis_client.incr(day_key))
            if n == 1:
                redis_client.expire(day_key, _DAY_TTL)
            if cooldown > 0:
                redis_client.set(f"ai:quota:build:cd:{user.id}", 1, ex=cooldown)
        except Exception:  # 记账失败不应阻断已成功派发的任务
            pass

    # ---------- internal ----------

    def _check_build_budget(self, user: Account) -> None:
        """灌库 / 重索引预算：先冷却、后日次数。redis 不可用时放行（fail-open）。"""
        cooldown = int(current_app.config.get("QUOTA_BUILD_COOLDOWN_SECONDS", 600))
        daily = int(current_app.config.get("QUOTA_BUILD_DAILY_LIMIT", 3))
        # 冷却：record_build 时写的 cd key 还在 → 拒绝
        try:
            if cooldown > 0 and redis_client.exists(f"ai:quota:build:cd:{user.id}"):
                minutes = max(1, cooldown // 60)
                raise ValidateErrorException(
                    message=f"灌库过于频繁，请间隔约 {minutes} 分钟后再试"
                )
        except ValidateErrorException:
            raise
        except Exception:
            pass  # redis 故障：冷却放行
        # 日次数：已记账数 ≥ 上限则拒（只读，不自增，自增在 record_build）。daily<=0 表示不限
        if daily <= 0:
            return
        try:
            used = int(redis_client.get(f"ai:quota:build:day:{user.id}:{datetime.utcnow().strftime('%Y%m%d')}") or 0)
        except Exception:
            used = 0  # redis 故障：日限放行
        if used >= daily:
            raise ValidateErrorException(
                message=f"今日灌库 / 重新索引次数已达上限（每天 {daily} 次），请明天再试或联系管理员"
            )

    @staticmethod
    def _incr_window(key: str, ttl: int, limit: int, message: str, exc=ValidateErrorException) -> None:
        """定长窗口计数：INCR，首次设 TTL；超过 limit 抛 exc。redis 故障则放行。

        exc 默认 ValidateErrorException(422，站内检索用)；对外接口可传 RateLimitException(429)。
        """
        try:
            n = int(redis_client.incr(key))
            if n == 1:
                redis_client.expire(key, ttl)
        except Exception:
            return  # redis 不可用：放行，不阻断
        if n > limit:
            raise exc(message=message)
