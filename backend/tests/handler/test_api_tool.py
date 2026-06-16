"""Phase 4c：自定义 API 工具 / 插件（CRUD + OpenAPI 解析 + 公共插件商店，user_id 隔离）。

重点验证：插件发布已拍平为「仅登录」（任意登录用户可发布自己的插件，无管理员门）。
"""
import json

import pytest

_SCHEMA = json.dumps({
    "server": "https://api.example.com",
    "description": "天气查询工具",
    "paths": {
        "/weather": {
            "get": {
                "operationId": "getWeather",
                "description": "查询某城市天气",
                "parameters": [
                    {"name": "city", "in": "query", "description": "城市名", "required": True, "type": "str"},
                ],
            }
        }
    },
})


def _create_provider(client, headers, name="wx"):
    r = client.post("/api/api-tools", headers=headers, json={
        "name": name, "icon": "https://i/x.png", "openapi_schema": _SCHEMA, "headers": [],
    })
    assert r.status_code == 200, r.get_data(as_text=True)
    # service 不回 id，从列表取
    lst = client.get("/api/api-tools", headers=headers).get_json()["data"]["list"]
    return next(p for p in lst if p["name"] == name)


def test_validate_openapi_schema(client, auth_headers):
    assert client.post("/api/api-tools/validate-openapi-schema", headers=auth_headers,
                       json={"openapi_schema": _SCHEMA}).status_code == 200
    # 非法 schema（paths 为空）→ 422
    bad = json.dumps({"server": "https://x", "description": "d", "paths": {}})
    assert client.post("/api/api-tools/validate-openapi-schema", headers=auth_headers,
                       json={"openapi_schema": bad}).status_code == 422


def test_api_tool_crud_and_isolation(client, auth_headers, other_headers):
    prov = _create_provider(client, auth_headers, "wx")
    pid = prov["id"]
    assert any(t["name"] == "getWeather" for t in prov["tools"])
    assert prov["is_public"] is False

    # 工具详情
    tool = client.get(f"/api/api-tools/{pid}/tools/getWeather", headers=auth_headers)
    assert tool.status_code == 200 and tool.get_json()["data"]["name"] == "getWeather"

    # 同名重复创建 → 422
    assert client.post("/api/api-tools", headers=auth_headers, json={
        "name": "wx", "icon": "https://i/x.png", "openapi_schema": _SCHEMA, "headers": [],
    }).status_code == 422

    # 归属隔离：他人看不到 / 改不了（404，不泄存在性）
    assert client.get(f"/api/api-tools/{pid}", headers=other_headers).status_code == 404
    assert client.post(f"/api/api-tools/{pid}/delete", headers=other_headers).status_code == 404

    # 自己删
    assert client.post(f"/api/api-tools/{pid}/delete", headers=auth_headers).status_code == 200
    assert client.get(f"/api/api-tools/{pid}", headers=auth_headers).status_code == 404


def test_plugin_store_publish_flatten_and_add(client, auth_headers, other_headers):
    """拍平验证：非管理员（本项目所有账号）也能把自有插件发布到商店；他人可添加回自己私有表。"""
    prov = _create_provider(client, auth_headers, "wx-pub")
    pid = prov["id"]

    # 发布（拍平：无管理员门，任意登录用户可发自有插件）
    assert client.post(f"/api/api-tools/{pid}/publish", headers=auth_headers,
                       json={"is_public": True}).status_code == 200

    # 自有列表里该 provider 标记 is_public=True
    mine = client.get("/api/api-tools", headers=auth_headers).get_json()["data"]["list"]
    assert next(p for p in mine if p["id"] == pid)["is_public"] is True

    # 商店列表含它；发布者自身未「添加」过（added=False）
    store = client.get("/api/plugin-store", headers=auth_headers).get_json()["data"]["list"]
    entry = next(p for p in store if p["name"] == "wx-pub")
    assert entry["added"] is False
    public_id = entry["id"]

    # 他人添加到自己私有表
    assert client.post(f"/api/plugin-store/{public_id}/add", headers=other_headers).status_code == 200
    other_list = client.get("/api/api-tools", headers=other_headers).get_json()["data"]["list"]
    assert any(p["name"] == "wx-pub" for p in other_list)
    # 商店对他人显示 added=True，重复添加 → 422
    store2 = client.get("/api/plugin-store", headers=other_headers).get_json()["data"]["list"]
    assert next(p for p in store2 if p["id"] == public_id)["added"] is True
    assert client.post(f"/api/plugin-store/{public_id}/add", headers=other_headers).status_code == 422

    # 取消发布 → 商店移除
    assert client.post(f"/api/api-tools/{pid}/publish", headers=auth_headers,
                       json={"is_public": False}).status_code == 200
    store3 = client.get("/api/plugin-store", headers=auth_headers).get_json()["data"]["list"]
    assert not any(p["id"] == public_id for p in store3)

    # 清理私有 provider
    client.post(f"/api/api-tools/{pid}/delete", headers=auth_headers)


def test_api_tool_require_login(client):
    assert client.get("/api/api-tools").status_code == 401
