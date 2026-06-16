"""自定义 API 工具的出站 HTTP 安全封装：超时 + SSRF 防护。

朴素的 requests.request 无超时、无 URL 校验；部署在公网时有两类风险：
① 慢/挂起的第三方接口拖垮 SSE 对话；② 用户可填内网地址探测容器内部服务
（应用网关 / mysql / redis / 169.254.169.254 等）。本模块在真正发请求前：
- 仅允许 http/https；
- 解析 host 的所有 IP，任一落在 loopback/私网/link-local/保留段即拒绝；
- 给 requests 加默认超时（可经 API_TOOL_HTTP_TIMEOUT 覆盖）。

注：解析与连接之间存在 DNS rebinding 的理论窗口（TOCTOU），本期作为基础防护可接受。
"""
from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urljoin, urlparse

import requests

# 出站请求超时（秒），可经环境变量覆盖
API_TOOL_HTTP_TIMEOUT = float(os.getenv("API_TOOL_HTTP_TIMEOUT") or 10)
# 最大重定向跳数（每一跳都会重新做 SSRF 校验），可经环境变量覆盖
API_TOOL_MAX_REDIRECTS = int(os.getenv("API_TOOL_MAX_REDIRECTS") or 5)


class UnsafeRequestError(Exception):
    """目标 URL 未通过安全校验（scheme 非法 / 指向内网）。"""


def _is_blocked_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def assert_safe_url(url: str) -> None:
    """校验 url 的 scheme 与目标 IP；不安全则抛 UnsafeRequestError。"""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeRequestError(f"仅支持 http/https，收到 {parsed.scheme or '空'}")
    host = parsed.hostname
    if not host:
        raise UnsafeRequestError("URL 缺少主机名")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise UnsafeRequestError(f"无法解析主机：{host}")
    for info in infos:
        ip = info[4][0]
        if _is_blocked_ip(ip):
            raise UnsafeRequestError(f"禁止访问内网/保留地址：{host} → {ip}")


def safe_request(method: str, url: str, **kwargs) -> requests.Response:
    """SSRF 校验后发起带超时的请求。

    requests 默认 allow_redirects=True，只在首跳前校验 URL 无法防住
    「302 跳转到内网/云元数据地址」的绕过；因此这里关闭自动重定向，手动逐跳跟随，
    并对每一个 Location 重新执行 assert_safe_url。
    """
    kwargs.setdefault("timeout", API_TOOL_HTTP_TIMEOUT)
    # 调用方若显式传入 allow_redirects 以其为准（仍逐跳校验）；默认自行跟随。
    follow_redirects = kwargs.pop("allow_redirects", True)

    current_method = method
    current_url = url
    for _ in range(API_TOOL_MAX_REDIRECTS + 1):
        assert_safe_url(current_url)
        resp = requests.request(method=current_method, url=current_url, allow_redirects=False, **kwargs)

        location = resp.headers.get("location")
        if not (follow_redirects and resp.is_redirect and location):
            return resp

        # 解析相对跳转并在下一轮循环开头重新做 SSRF 校验
        current_url = urljoin(current_url, location)
        # 301/302/303 对非 GET/HEAD 通常降级为 GET，且应丢弃原请求体
        if resp.status_code in (301, 302, 303) and current_method.upper() not in ("GET", "HEAD"):
            current_method = "GET"
            kwargs.pop("data", None)
            kwargs.pop("json", None)
            kwargs.pop("files", None)

    raise UnsafeRequestError(f"重定向次数超过上限（{API_TOOL_MAX_REDIRECTS}）")
