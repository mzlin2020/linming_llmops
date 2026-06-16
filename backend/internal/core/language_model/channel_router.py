"""多渠道兜底的健康仲裁 + 失败转移聊天模型（仅 multi_channel provider 用）。

熔断状态全在 redis（db2），热路径**不写 DB**：
- ai:llm:chan:<id>:fails    连续失败计数（成功即清零）
- ai:llm:chan:<id>:disabled 存在即熔断（SET EX=冷却秒；TTL 到期自动「半开」重试，无需定时任务）
- ai:llm:chan:<id>:err      最近一次错误摘要（与 disabled 同 TTL，供后台展示）

错误分级：只有渠道级故障（连接错/超时/5xx/401/403/429）才 failover + 计入失败；
请求自身 4xx（400/422 参数错、内容审查拒绝）直接抛出、不切渠道（换渠道也会同样失败）。

FailoverChatModel 是 duck-typed（非 BaseChatModel 子类）——chat/agent/workflow 三条链路只用到
bind_tools / stream / invoke，与本仓库 test/conftest 里的假模型同一契约，最稳。
"""
from __future__ import annotations

from typing import Any, Callable

from internal.exception import FailException
from internal.extension.redis_extension import redis_client


def _fail_key(cid: int) -> str:
    return f"ai:llm:chan:{cid}:fails"


def _disabled_key(cid: int) -> str:
    return f"ai:llm:chan:{cid}:disabled"


def _err_key(cid: int) -> str:
    return f"ai:llm:chan:{cid}:err"


class ChannelRouter:
    def __init__(self, threshold: int = 3, cooldown: int = 300):
        self.threshold = max(1, int(threshold))
        self.cooldown = max(1, int(cooldown))
        self.redis = redis_client

    def is_disabled(self, cid: int) -> bool:
        try:
            return bool(self.redis.exists(_disabled_key(cid)))
        except Exception:
            return False  # redis 失联 → 视为可用（宁可放行也不全熔断卡死对话）

    def filter_live(self, items: list[tuple]) -> list[tuple]:
        """items: [(channel_id, payload)...]；剔除当前熔断的，保持原优先级顺序。"""
        return [it for it in items if not self.is_disabled(it[0])]

    def record_success(self, cid: int) -> None:
        try:
            self.redis.delete(_fail_key(cid), _disabled_key(cid), _err_key(cid))
        except Exception:
            pass

    def record_failure(self, cid: int, err: Any) -> None:
        try:
            n = int(self.redis.incr(_fail_key(cid)))
            self.redis.expire(_fail_key(cid), self.cooldown * 5)  # 计数窗口，避免历史失败永久累加
            if n >= self.threshold:
                self.redis.set(_disabled_key(cid), "1", ex=self.cooldown)
                self.redis.set(_err_key(cid), str(err)[:480], ex=self.cooldown)
        except Exception:
            pass

    def recover(self, cid: int) -> None:
        """手动恢复：清掉熔断/计数（后台「手动恢复」按钮调用）。"""
        self.record_success(cid)

    def health(self, cid: int) -> dict:
        """供后台展示：是否熔断 + 剩余冷却秒 + 失败计数 + 最近错误。redis 失联回 unknown。"""
        try:
            disabled = bool(self.redis.exists(_disabled_key(cid)))
            ttl = int(self.redis.ttl(_disabled_key(cid))) if disabled else 0
            fails_raw = self.redis.get(_fail_key(cid))
            err_raw = self.redis.get(_err_key(cid))
            err = err_raw.decode("utf-8", "ignore") if isinstance(err_raw, bytes) else (err_raw or "")
            return {
                "status": "disabled" if disabled else "ok",
                "cooldown_remaining": max(0, ttl),
                "consecutive_failures": int(fails_raw) if fails_raw else 0,
                "last_error": err,
            }
        except Exception:
            return {"status": "unknown", "cooldown_remaining": 0, "consecutive_failures": 0, "last_error": ""}

    def run(self, candidates: list[tuple], call):
        """按序在健康候选间失败转移：candidates=[(id, item)...]，call(item)->result。
        渠道级故障 record_failure 后试下一个；成功 record_success 返回；全失败抛最后一个异常。
        （流式有「首 token 后不可切」语义，不走这里，见 FailoverChatModel.stream。）"""
        live = self.filter_live(candidates)
        if not live:
            raise FailException(message="无可用渠道（全部熔断或禁用）")
        last: BaseException | None = None
        for cid, item in live:
            try:
                res = call(item)
            except Exception as e:
                if not self.is_channel_error(e):
                    raise
                self.record_failure(cid, e)
                last = e
                continue
            self.record_success(cid)
            return res
        raise last or FailException(message="无可用渠道")

    @staticmethod
    def is_channel_error(exc: BaseException) -> bool:
        """是否渠道级故障（应 failover + 计熔断）。请求自身 4xx 返回 False（不切渠道）。"""
        status = getattr(exc, "status_code", None)
        if status is None:
            status = getattr(getattr(exc, "response", None), "status_code", None)
        name = type(exc).__name__.lower()
        if status in (400, 422) or "badrequest" in name or "unprocessable" in name:
            return False
        if status in (401, 403, 408, 409, 425, 429):
            return True
        if isinstance(status, int):
            if 500 <= status < 600:
                return True
            if 400 <= status < 500:
                return False  # 其它 4xx 视为请求自身问题，不切渠道
        # 无状态码（连接错 / 超时 / DNS / 读超时等）→ 渠道级
        return True


class FailoverChatModel:
    """按优先级在多个渠道（已是各自 base_url/key 的 ChatModel）间失败转移的聊天模型。

    invoke / stream 透明兜底；bind_tools 把工具绑到每个渠道后返回新的 FailoverChatModel。
    流式：只在「首 token 到达前」的连接/早期错误上切渠道；一旦开吐字再断，按错误上报（不透明重试，
    否则会重复输出）。同步 invoke 可整次切。
    """

    def __init__(self, channels: list[tuple], router: ChannelRouter, model_name: str = ""):
        self._channels = channels  # [(channel_id, runnable)]
        self._router = router
        self.model_name = model_name

    def bind_tools(self, tools: Any, **kwargs: Any) -> "FailoverChatModel":
        bound = [(cid, r.bind_tools(tools, **kwargs)) for cid, r in self._channels]
        return FailoverChatModel(bound, self._router, self.model_name)

    def _live(self) -> list[tuple]:
        return self._router.filter_live(self._channels)

    def invoke(self, input: Any, **kwargs: Any) -> Any:
        return self._router.run(self._channels, lambda r: r.invoke(input, **kwargs))

    def stream(self, input: Any, **kwargs: Any):
        live = self._live()
        if not live:
            raise FailException(message="无可用渠道（全部熔断或禁用）")
        last: BaseException | None = None
        for cid, r in live:
            try:
                it = iter(r.stream(input, **kwargs))
                first = next(it)
            except StopIteration:
                self._router.record_success(cid)
                return
            except Exception as e:
                if not self._router.is_channel_error(e):
                    raise
                self._router.record_failure(cid, e)
                last = e
                continue
            # 拿到首块 → 锁定该渠道，后续不再切（已开吐字，再切会重复输出）
            yield first
            try:
                for chunk in it:
                    yield chunk
            except Exception as e:
                self._router.record_failure(cid, e)
                raise
            self._router.record_success(cid)
            return
        raise last or FailException(message="无可用渠道")
