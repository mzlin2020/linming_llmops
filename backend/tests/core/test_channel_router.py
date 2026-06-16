"""多渠道熔断 + 失败转移（channel_router）。用内存假 redis 让熔断计数可断言。"""
import pytest

from internal.core.language_model.channel_router import ChannelRouter, FailoverChatModel


class _FakeRedis:
    def __init__(self):
        self.store = {}
        self.expiry = {}

    def exists(self, k):
        return 1 if k in self.store else 0

    def incr(self, k):
        self.store[k] = int(self.store.get(k, 0)) + 1
        return self.store[k]

    def expire(self, k, s):
        self.expiry[k] = s

    def set(self, k, v, ex=None):
        self.store[k] = v
        if ex is not None:
            self.expiry[k] = ex

    def get(self, k):
        return self.store.get(k)

    def delete(self, *ks):
        for k in ks:
            self.store.pop(k, None)
            self.expiry.pop(k, None)

    def ttl(self, k):
        return self.expiry.get(k, -1)


class _Err(Exception):
    def __init__(self, status=None):
        self.status_code = status
        super().__init__(f"err{status}")


def _router(threshold=2, cooldown=300):
    r = ChannelRouter(threshold=threshold, cooldown=cooldown)
    r.redis = _FakeRedis()
    return r


# --------------------------- 错误分级（纯静态，无 redis）---------------------------
@pytest.mark.parametrize("status,expected", [
    (400, False), (422, False),           # 请求自身 4xx → 不切渠道
    (401, True), (403, True), (429, True), (408, True),
    (500, True), (503, True),             # 5xx → 渠道级
    (None, True),                          # 连接错/超时（无状态码）→ 渠道级
])
def test_is_channel_error(status, expected):
    assert ChannelRouter.is_channel_error(_Err(status)) is expected


def test_is_channel_error_by_name():
    class BadRequestError(Exception):
        pass
    assert ChannelRouter.is_channel_error(BadRequestError()) is False


# --------------------------- 熔断计数 ---------------------------
def test_circuit_breaks_after_threshold():
    r = _router(threshold=2, cooldown=300)
    assert r.is_disabled(7) is False
    r.record_failure(7, _Err(500))
    assert r.is_disabled(7) is False           # 1 次未达阈值
    r.record_failure(7, _Err(500))
    assert r.is_disabled(7) is True            # 2 次 → 熔断
    health = r.health(7)
    assert health["status"] == "disabled"
    assert health["consecutive_failures"] >= 2
    r.record_success(7)                         # 成功即清零 + 解除熔断
    assert r.is_disabled(7) is False


# --------------------------- run 失败转移 ---------------------------
def test_run_failover_skips_bad_channel():
    r = _router(threshold=5)
    candidates = [(1, "ch1"), (2, "ch2")]

    def call(item):
        if item == "ch1":
            raise _Err(503)   # 渠道级 → 切下一个
        return f"done:{item}"

    assert r.run(candidates, call) == "done:ch2"


def test_run_request_4xx_propagates_without_failover():
    r = _router()
    calls = []

    def call(item):
        calls.append(item)
        raise _Err(400)       # 请求自身错 → 直接抛，不切渠道

    with pytest.raises(_Err):
        r.run([(1, "ch1"), (2, "ch2")], call)
    assert calls == ["ch1"]    # 只试了第一个就抛出


# --------------------------- FailoverChatModel ---------------------------
class _RB:
    def __init__(self, name, fail=False):
        self.name = name
        self.fail = fail

    def invoke(self, inp, **kw):
        if self.fail:
            raise _Err(503)
        return f"{self.name}:{inp}"

    def stream(self, inp, **kw):
        if self.fail:
            raise _Err(503)
        yield f"{self.name}-a"
        yield f"{self.name}-b"


def test_failover_chat_invoke():
    r = _router(threshold=5)
    fcm = FailoverChatModel([(1, _RB("bad", fail=True)), (2, _RB("good"))], r)
    assert fcm.invoke("hi") == "good:hi"


def test_failover_chat_stream():
    r = _router(threshold=5)
    fcm = FailoverChatModel([(1, _RB("bad", fail=True)), (2, _RB("good"))], r)
    chunks = list(fcm.stream("hi"))
    assert chunks == ["good-a", "good-b"]
