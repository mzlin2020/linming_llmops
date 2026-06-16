"""Phase 4c：开放 API（/api/openapi/*，API-Key 鉴权链路 + EndUser 隔离 + 委托 ChatService 内核）。

本机可跑：fake_llm 走裸 LLM 流（不触 Agent/工具/redis）；openapi 限速 redis fail-open 放行。
"""
import json


def _create_app(client, headers, name="openapi-app"):
    r = client.post("/api/apps", headers=headers, json={"name": name})
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()["data"]


def _publish(client, headers, app_id):
    assert client.post(f"/api/apps/{app_id}/publish", headers=headers).status_code == 200


def _sse_events(text: str) -> list[str]:
    return [ln.split("event: ", 1)[1] for ln in text.splitlines() if ln.startswith("event: ")]


def _first_ping_meta(text: str) -> dict:
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln == "event: ping":
            return json.loads(lines[i + 1].split("data: ", 1)[1])
    return {}


def _setup(client, make_account, make_token, publish=True):
    aid = make_account()
    jwt = {"Authorization": f"Bearer {make_token(aid)}"}
    app_id = _create_app(client, jwt)["id"]
    if publish:
        _publish(client, jwt, app_id)
    return aid, jwt, app_id


# ---------------- 鉴权链路 ----------------

def test_openapi_missing_key(client, make_account, make_token):
    _, _, app_id = _setup(client, make_account, make_token)
    assert client.post("/api/openapi/chat", json={"app_id": app_id, "query": "hi"}).status_code == 401


def test_openapi_invalid_key(client, make_account, make_token):
    _, _, app_id = _setup(client, make_account, make_token)
    r = client.post("/api/openapi/chat", headers={"Authorization": "Bearer ak-v1/bogus"},
                    json={"app_id": app_id, "query": "hi"})
    assert r.status_code == 401


def test_openapi_inactive_key(client, make_account, make_token, fake_llm):
    aid, jwt, app_id = _setup(client, make_account, make_token)
    created = client.post("/api/api-keys", headers=jwt, json={}).get_json()["data"]
    key, kid = created["api_key"], created["id"]
    client.post(f"/api/api-keys/{kid}", headers=jwt, json={"is_active": False})  # 停用
    r = client.post("/api/openapi/chat", headers={"Authorization": f"Bearer {key}"},
                    json={"app_id": app_id, "query": "hi"})
    assert r.status_code == 401


def test_openapi_cross_account_forbidden(client, make_account, make_token, make_api_key, fake_llm):
    _, _, app_id = _setup(client, make_account, make_token)
    other_key = make_api_key(make_account())  # 他人账号的 key
    r = client.post("/api/openapi/chat", headers={"Authorization": f"Bearer {other_key}"},
                    json={"app_id": app_id, "query": "hi"})
    assert r.status_code == 403


# ---------------- app-info ----------------

def test_openapi_app_info(client, make_account, make_token, make_api_key):
    aid, _, app_id = _setup(client, make_account, make_token)
    kh = {"Authorization": f"Bearer {make_api_key(aid)}"}
    r = client.get(f"/api/openapi/app-info?app_id={app_id}", headers=kh)
    assert r.status_code == 200, r.get_data(as_text=True)
    assert "opening_statement" in r.get_json()["data"]


def test_openapi_app_info_unpublished_404(client, make_account, make_token, make_api_key):
    aid, _, app_id = _setup(client, make_account, make_token, publish=False)
    kh = {"Authorization": f"Bearer {make_api_key(aid)}"}
    assert client.get(f"/api/openapi/app-info?app_id={app_id}", headers=kh).status_code == 404


# ---------------- chat（SSE / 同步 / 终端用户复用）----------------

def test_openapi_chat_stream(client, make_account, make_token, make_api_key, fake_llm, no_after_round_dispatch):
    aid, _, app_id = _setup(client, make_account, make_token)
    kh = {"Authorization": f"Bearer {make_api_key(aid)}"}
    r = client.post("/api/openapi/chat", headers=kh,
                    json={"app_id": app_id, "query": "hi", "stream": True})
    assert r.status_code == 200, r.get_data(as_text=True)
    text = r.get_data(as_text=True)
    events = _sse_events(text)
    assert "ping" in events and "message" in events and "agent_end" in events
    meta = _first_ping_meta(text)
    assert meta.get("conversation_id") and meta.get("end_user_id")


def test_openapi_chat_complete(client, make_account, make_token, make_api_key, fake_llm, no_after_round_dispatch):
    aid, _, app_id = _setup(client, make_account, make_token)
    kh = {"Authorization": f"Bearer {make_api_key(aid)}"}
    r = client.post("/api/openapi/chat", headers=kh,
                    json={"app_id": app_id, "query": "hi", "stream": False})
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()["data"]
    assert data["answer"] and data["end_user_id"] and data["conversation_id"]


def test_openapi_chat_end_user_reuse_and_isolation(
    client, make_account, make_token, make_api_key, make_end_user, fake_llm, no_after_round_dispatch,
):
    aid, _, app_id = _setup(client, make_account, make_token)
    kh = {"Authorization": f"Bearer {make_api_key(aid)}"}
    # 首轮：自动建终端用户 + 会话
    first = _first_ping_meta(client.post("/api/openapi/chat", headers=kh,
                                         json={"app_id": app_id, "query": "hi", "stream": True}).get_data(as_text=True))
    euid, conv_id = first["end_user_id"], first["conversation_id"]
    # 复用同一终端用户 + 会话续聊
    r2 = client.post("/api/openapi/chat", headers=kh, json={
        "app_id": app_id, "query": "again", "stream": False,
        "end_user_id": euid, "conversation_id": conv_id,
    })
    assert r2.status_code == 200 and r2.get_json()["data"]["conversation_id"] == conv_id
    # 传他人 app 下的终端用户 id → 拒（归属不匹配）
    other_aid = make_account()
    foreign_euid = make_end_user(other_aid, app_id)
    bad = client.post("/api/openapi/chat", headers=kh, json={
        "app_id": app_id, "query": "x", "stream": False, "end_user_id": foreign_euid,
    })
    assert bad.status_code == 403
