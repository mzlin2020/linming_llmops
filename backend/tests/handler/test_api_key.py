"""Phase 4c：开放 API 密钥（account 自管自己的密钥，JWT 保护）。"""


def test_api_key_crud_and_isolation(client, auth_headers, other_headers):
    # 创建 → 返回明文 key，前缀来自配置 API_KEY_PREFIX（默认 ak-v1/）
    created = client.post("/api/api-keys", headers=auth_headers,
                          json={"remark": "k1"}).get_json()["data"]
    assert created["api_key"].startswith("ak-v1/")
    assert created["is_active"] is True and created["remark"] == "k1"
    key_id = created["id"]

    # 列表只含自己的
    lst = client.get("/api/api-keys", headers=auth_headers).get_json()["data"]["list"]
    assert any(k["id"] == key_id for k in lst)
    assert client.get("/api/api-keys", headers=other_headers).get_json()["data"]["list"] == []

    # 改备注 / 停用
    upd = client.post(f"/api/api-keys/{key_id}", headers=auth_headers,
                      json={"remark": "k1-x", "is_active": False}).get_json()["data"]
    assert upd["remark"] == "k1-x" and upd["is_active"] is False

    # 他人无权改 / 删（归属隔离 → 403）
    assert client.post(f"/api/api-keys/{key_id}", headers=other_headers,
                       json={"remark": "hack"}).status_code == 403
    assert client.post(f"/api/api-keys/{key_id}/delete", headers=other_headers).status_code == 403

    # 自己删
    assert client.post(f"/api/api-keys/{key_id}/delete", headers=auth_headers).status_code == 200
    assert client.get("/api/api-keys", headers=auth_headers).get_json()["data"]["list"] == []


def test_api_key_require_login(client):
    assert client.get("/api/api-keys").status_code == 401
    assert client.post("/api/api-keys", json={}).status_code == 401
