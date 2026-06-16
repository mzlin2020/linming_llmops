"""Phase 4c：语言模型目录（只读，恒开）+ llm_admin 写入面（ENABLE_LLM_ADMIN 部署级开关守护）。

本机可跑（bump_version / channel_router 健康均 redis fail-open；crypto 用 AI_SECRET_ENCRYPT_KEY）。
"""


# ---------------- language_model（只读目录）----------------

def test_language_models_list(client, auth_headers):
    """空目录（测试库无 provider 种子）→ 返回列表，200。"""
    r = client.get("/api/language-models", headers=auth_headers)
    assert r.status_code == 200, r.get_data(as_text=True)
    assert isinstance(r.get_json()["data"], list)


def test_language_models_require_login(client):
    assert client.get("/api/language-models").status_code == 401


# ---------------- llm_admin（写入面：env 开关）----------------

def test_llm_admin_disabled_by_default(client, auth_headers):
    """ENABLE_LLM_ADMIN 默认关 → 写入面（含只读列表）一律 403。"""
    assert client.get("/api/admin/llm-providers", headers=auth_headers).status_code == 403
    assert client.post("/api/admin/llm-providers", headers=auth_headers,
                       json={"name": "p1", "protocol": "openai"}).status_code == 403
    assert client.get("/api/admin/llm-protocols", headers=auth_headers).status_code == 403


def test_llm_admin_requires_login_even_when_enabled(client, app, monkeypatch):
    monkeypatch.setitem(app.config, "ENABLE_LLM_ADMIN", True)
    assert client.get("/api/admin/llm-providers").status_code == 401


def test_llm_admin_enabled_crud(client, auth_headers, app, monkeypatch):
    monkeypatch.setitem(app.config, "ENABLE_LLM_ADMIN", True)

    # 协议白名单：含 openai，且已去厂商化（不含 volc/火山等）
    protos = client.get("/api/admin/llm-protocols", headers=auth_headers).get_json()["data"]
    assert "openai" in protos
    assert not any("volc" in p for p in protos)

    # 建 provider：明文 api_key 加密落库，响应只回掩码（绝不回明文）
    p = client.post("/api/admin/llm-providers", headers=auth_headers, json={
        "name": "myp", "protocol": "openai", "api_key": "sk-supersecret", "base_url": "https://x",
    })
    assert p.status_code == 200, p.get_data(as_text=True)
    p = p.get_json()["data"]
    pid = p["id"]
    assert p["has_api_key"] is True
    assert "sk-supersecret" not in (p["api_key_mask"] or "")

    try:
        # 重复 name → 422
        assert client.post("/api/admin/llm-providers", headers=auth_headers,
                           json={"name": "myp", "protocol": "openai"}).status_code == 422
        # 非法协议 → 422
        assert client.post("/api/admin/llm-providers", headers=auth_headers,
                           json={"name": "myp2", "protocol": "nope"}).status_code == 422

        # 建 model
        m = client.post(f"/api/admin/llm-providers/{pid}/models", headers=auth_headers,
                        json={"model_name": "gpt-x", "model_type": "chat"})
        assert m.status_code == 200, m.get_data(as_text=True)
        mid = m.get_json()["data"]["id"]
        assert m.get_json()["data"]["model_name"] == "gpt-x"

        # 列表里能看到该 provider 及其 model
        providers = client.get("/api/admin/llm-providers", headers=auth_headers).get_json()["data"]
        mine = next(x for x in providers if x["id"] == pid)
        assert any(mm["id"] == mid for mm in mine["models"])

        # 删 model
        assert client.post(f"/api/admin/llm-models/{mid}/delete", headers=auth_headers).status_code == 200
    finally:
        # 清理：删 provider（FK CASCADE 连带删 model/channel），避免污染同 session 其它用例
        client.post(f"/api/admin/llm-providers/{pid}/delete", headers=auth_headers)
