"""Phase 4c：内置工具目录（只读）+ 全站统计（公开）。

本机可跑（不连 redis/Qdrant：stats 的 redis 缓存 fail-open 现算）。
"""


# ---------------- 内置工具目录 ----------------

def test_builtin_tools_catalog(client, auth_headers):
    r = client.get("/api/builtin-tools", headers=auth_headers)
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()["data"]
    assert isinstance(data, list) and len(data) >= 1
    names = {p["name"] for p in data}
    # 厂商专有 provider（高德 gaode）已在核心层删除，目录里不应出现
    assert "gaode" not in names
    # 通用零依赖工具 time/current_time 应在（与默认 app 配置一致）
    assert "time" in names


def test_builtin_categories(client, auth_headers):
    r = client.get("/api/builtin-tools/categories", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.get_json()["data"], list)


def test_builtin_tool_detail_404(client, auth_headers):
    assert client.get("/api/builtin-tools/nope/tools/x", headers=auth_headers).status_code == 404


def test_builtin_tools_require_login(client):
    assert client.get("/api/builtin-tools").status_code == 401


# ---------------- 全站统计 ----------------

def test_stats_public_no_login(client):
    """/api/stats 公开端点（无需登录）；redis 不可用时 fail-open 现算返回。"""
    r = client.get("/api/stats")
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()["data"]
    for k in ("app_count", "plugin_count", "builtin_tool_count",
              "dataset_count", "image_count", "workflow_count"):
        assert k in data and isinstance(data[k], int)
    assert data["builtin_tool_count"] >= 1  # 至少内置 time 工具
