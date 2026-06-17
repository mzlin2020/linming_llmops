"""Phase 8c：图像生成 文生图 / 图生图 / 画廊 / 能力 URL 取图（user_id 隔离）。

本机可跑：mock 掉 LanguageModelManager.generate_images（不连上游）+ requests.get（不下载），
STORAGE_ROOT 指向 tmp_path（落地隔离）。配额 check_image_generation 在 redis 不可用时 fail-open 放行。
真实上游/网络/容器链路交 CI / 真机。
"""
import re

import pytest
import requests as _requests

from internal.core.language_model import LanguageModelManager

FAKE_BYTES = b"\x89PNG\r\n\x1a\nfake-image-bytes"


class _FakeResp:
    content = FAKE_BYTES
    headers = {"Content-Type": "image/png"}

    def raise_for_status(self):
        return None


@pytest.fixture
def image_env(app, monkeypatch, tmp_path):
    """配好生图模型 + mock 上游出图与下载 + 落地到 tmp。"""
    monkeypatch.setitem(app.config, "DEFAULT_IMAGE_PROVIDER", "openai")
    monkeypatch.setitem(app.config, "DEFAULT_IMAGE_MODEL", "dall-e-3")
    monkeypatch.setitem(app.config, "STORAGE_ROOT", str(tmp_path))
    monkeypatch.setattr(
        LanguageModelManager, "generate_images",
        lambda self, provider, model, prompt, *, image=None, **kw: [{"url": "http://upstream.local/x.png"}],
    )
    monkeypatch.setattr(_requests, "get", lambda *a, **k: _FakeResp())
    return app


# ---------------- 文生图 + 能力 URL 取图 ----------------

def test_text_to_image_creates_record_and_serves(client, auth_headers, image_env):
    r = client.post("/api/images/text-to-image", headers=auth_headers,
                    json={"prompt": "一只赛博朋克的猫", "size": "1024x1024"})
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()["data"]
    assert data["type"] == "text2img" and data["prompt"] == "一只赛博朋克的猫"
    assert re.fullmatch(r"/api/images/file/[0-9a-f]{32}\.png", data["url"])

    # 能力 URL 取图：不带任何登录头也能拿到（供 <img> / Agent markdown 加载）
    name = data["url"].rsplit("/", 1)[-1]
    g = client.get(f"/api/images/file/{name}")
    assert g.status_code == 200
    assert g.data == FAKE_BYTES
    assert g.headers["Content-Type"].startswith("image/png")


def test_serve_rejects_bad_or_missing_name(client, image_env):
    # 非 uuid 文件名 / 非法扩展名 → 404（regex 守卫）；路径穿越的 "/" 进不了 <string> 路由
    assert client.get("/api/images/file/notavaliduuid.png").status_code == 404
    assert client.get("/api/images/file/" + "a" * 32 + ".txt").status_code == 404
    # 合法格式但文件不存在 → 404
    assert client.get("/api/images/file/" + "a" * 32 + ".png").status_code == 404


def test_unconfigured_provider_returns_friendly_error(client, auth_headers, app, monkeypatch, tmp_path):
    monkeypatch.setitem(app.config, "DEFAULT_IMAGE_PROVIDER", "")
    monkeypatch.setitem(app.config, "DEFAULT_IMAGE_MODEL", "")
    monkeypatch.setitem(app.config, "STORAGE_ROOT", str(tmp_path))
    r = client.post("/api/images/text-to-image", headers=auth_headers, json={"prompt": "x"})
    assert r.status_code == 400, r.get_data(as_text=True)  # FailException，非 500
    assert "未配置" in r.get_json()["message"]


# ---------------- 鉴权 / 校验 ----------------

def test_generation_requires_login(client, image_env):
    assert client.post("/api/images/text-to-image", json={"prompt": "x"}).status_code == 401
    assert client.get("/api/images").status_code == 401


def test_prompt_validation(client, auth_headers, image_env):
    # 空 prompt → 422（schema min_length=1）
    assert client.post("/api/images/text-to-image", headers=auth_headers, json={"prompt": ""}).status_code == 422


def test_image_to_image_rejects_non_whitelisted_url(client, auth_headers, image_env):
    # 参考图 URL 不在白名单域名内 → 422（assert_url_allowed，先于配额/生图）
    r = client.post("/api/images/image-to-image", headers=auth_headers,
                    json={"prompt": "改成水彩", "image_url": "http://evil.local/x.png"})
    assert r.status_code == 422, r.get_data(as_text=True)


# ---------------- 画廊分页 + 归属隔离 ----------------

def test_gallery_lists_only_own_images(client, auth_headers, other_headers, image_env):
    def _gen(headers, prompt):
        rr = client.post("/api/images/text-to-image", headers=headers, json={"prompt": prompt})
        assert rr.status_code == 200, rr.get_data(as_text=True)
        return rr.get_json()["data"]["id"]

    mine = {_gen(auth_headers, "我的图A"), _gen(auth_headers, "我的图B")}
    theirs = _gen(other_headers, "别人的图")

    page = client.get("/api/images", headers=auth_headers).get_json()["data"]
    ids = {row["id"] for row in page["list"]}
    assert mine <= ids
    assert theirs not in ids
    assert page["paginator"]["total_record"] == 2

    # 对方只看得到自己的那张
    other_page = client.get("/api/images", headers=other_headers).get_json()["data"]
    assert {row["id"] for row in other_page["list"]} == {theirs}
