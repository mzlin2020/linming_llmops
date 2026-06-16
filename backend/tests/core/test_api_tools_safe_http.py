"""api_tools 出站 HTTP 安全封装：SSRF 校验 + 逐跳重定向复校（纯本机，不触网）。

字面 IP 经 socket.getaddrinfo 本地解析、无需 DNS；公网放行用字面公网 IP（8.8.8.8）验证；
重定向逐跳复校用 monkeypatch 替换 requests.request，模拟 302→环回，断言第二跳被拒。
"""
import pytest
import requests

from internal.core.tools.api_tools.entities import OpenAPISchema, ToolEntity
from internal.core.tools.api_tools.providers import ApiProviderManager
from internal.core.tools.api_tools.providers._safe_http import (
    UnsafeRequestError,
    assert_safe_url,
    safe_request,
)


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/admin",          # 环回
    "http://10.0.0.5/internal",        # 私网 A
    "http://192.168.1.1/",             # 私网 C
    "http://169.254.169.254/latest/meta-data/",  # 云元数据 link-local
    "http://[::1]/",                   # IPv6 环回
])
def test_assert_safe_url_blocks_internal(url):
    with pytest.raises(UnsafeRequestError):
        assert_safe_url(url)


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",   # 非 http/https
    "ftp://example.com/x",
    "http:///no-host",      # 缺主机名
])
def test_assert_safe_url_blocks_bad_scheme_or_host(url):
    with pytest.raises(UnsafeRequestError):
        assert_safe_url(url)


def test_assert_safe_url_allows_public_ip():
    # 字面公网 IP，本地解析、不触网；落在公网段即放行（不抛）
    assert_safe_url("http://8.8.8.8/api") is None


class _FakeResp:
    """最小化 requests.Response 替身：safe_request 只读 headers/is_redirect/status_code。"""
    def __init__(self, status_code=200, location=None):
        self.status_code = status_code
        self.headers = {"location": location} if location else {}
        self.is_redirect = location is not None
        self.text = "ok"


def test_safe_request_revalidates_each_redirect_hop(monkeypatch):
    # 首跳公网 8.8.8.8 通过 → 返回 302 跳转到环回；第二跳 assert_safe_url 必须拦下
    def fake_request(method, url, **kwargs):
        return _FakeResp(status_code=302, location="http://127.0.0.1/internal")

    monkeypatch.setattr(requests, "request", fake_request)
    with pytest.raises(UnsafeRequestError):
        safe_request("get", "http://8.8.8.8/start")


def test_safe_request_returns_non_redirect(monkeypatch):
    monkeypatch.setattr(requests, "request", lambda method, url, **kw: _FakeResp(status_code=200))
    resp = safe_request("get", "http://8.8.8.8/ok")
    assert resp.status_code == 200 and resp.text == "ok"


def test_openapi_schema_rejects_bad_operation_id():
    # operationId 含点 → 破坏 tool_call 工具名，必须拒
    from internal.exception import ValidateErrorException

    with pytest.raises(ValidateErrorException):
        OpenAPISchema(server="https://api.example.com", description="测试", paths={
            "/x": {"get": {"description": "d", "operationId": "bad.id", "parameters": []}},
        })


def test_api_provider_manager_builds_structured_tool():
    # ToolEntity → StructuredTool：工具名为 f"{id}_{operationId}"，args_schema 由 parameters 生成
    entity = ToolEntity(
        id="12", name="getWeather", url="https://api.example.com/weather",
        method="get", description="查询天气",
        parameters=[{"name": "city", "in": "query", "description": "城市", "required": True, "type": "str"}],
    )
    tool = ApiProviderManager().get_tool(entity)
    assert tool.name == "12_getWeather"
    assert "city" in tool.args_schema.model_fields
