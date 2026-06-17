"""Phase 8a：工作流 CRUD + 草稿图 + 调试(SSE) + 发布生命周期 + 应用装配（user_id 隔离）。

本机可跑：minimal_graph 用 template_transform（jinja 沙箱），调试不连 LLM/网络/Qdrant；
调试配额 check_workflow_debug 在 redis 不可用时 fail-open 放行。
"""
import uuid


# ---------------- 内联图工厂（与前端编辑器/核心层 JSON 同构；不跨包 import 测试工具）----------------

def _nid() -> str:
    return str(uuid.uuid4())


def _input_var(name, var_type="string", required=True, description=""):
    return {
        "name": name, "type": var_type, "required": required, "description": description,
        "value": {"type": "generated", "content": ""},
    }


def _ref_var(name, ref_node, ref_var_name, var_type="string", required=True):
    return {
        "name": name, "type": var_type, "required": required,
        "value": {"type": "ref", "content": {"ref_node_id": ref_node["id"], "ref_var_name": ref_var_name}},
    }


def _start(inputs=None, title="开始"):
    return {"id": _nid(), "node_type": "start", "title": title, "inputs": inputs or []}


def _template(template="", inputs=None, title="模板转换"):
    return {"id": _nid(), "node_type": "template_transform", "title": title,
            "template": template, "inputs": inputs or []}


def _end(outputs=None, title="结束"):
    return {"id": _nid(), "node_type": "end", "title": title, "outputs": outputs or []}


def _edge(src, dst):
    return {"id": _nid(), "source": src["id"], "source_type": src["node_type"],
            "target": dst["id"], "target_type": dst["node_type"]}


def _minimal_graph():
    """start(name) → template_transform(你好，{{ name }}) → end(text)。无 LLM/网络/DB。"""
    start = _start(inputs=[_input_var("name", description="你的名字")])
    template = _template(template="你好，{{ name }}", inputs=[_ref_var("name", start, "name")])
    end = _end(outputs=[_ref_var("text", template, "output")])
    return [start, template, end], [_edge(start, template), _edge(template, end)]


# ---------------- HTTP helpers ----------------

def _create(client, headers, tool_call_name, name="工作流", description="一个测试工作流"):
    r = client.post("/api/workflows", headers=headers, json={
        "name": name, "tool_call_name": tool_call_name, "description": description,
    })
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()["data"]["id"]


def _save_draft(client, headers, wf_id, nodes, edges):
    r = client.post(f"/api/workflows/{wf_id}/draft-graph", headers=headers,
                    json={"nodes": nodes, "edges": edges})
    assert r.status_code == 200, r.get_data(as_text=True)


def _detail(client, headers, wf_id):
    r = client.get(f"/api/workflows/{wf_id}", headers=headers)
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()["data"]


def _sse_events(text: str) -> list[str]:
    return [ln.split("event: ", 1)[1] for ln in text.splitlines() if ln.startswith("event: ")]


# ---------------- CRUD + 归属隔离 ----------------

def test_workflow_crud_and_isolation(client, auth_headers, other_headers):
    wf_id = _create(client, auth_headers, "wf_alpha", name="阿尔法")

    # 列表含 node_count（空草稿 = 0）
    lst = client.get("/api/workflows", headers=auth_headers).get_json()["data"]["list"]
    row = next(w for w in lst if w["id"] == wf_id)
    assert row["status"] == "draft" and row["node_count"] == 0 and row["is_debug_passed"] is False

    # 更新基础信息
    assert client.post(f"/api/workflows/{wf_id}", headers=auth_headers,
                       json={"name": "阿尔法2"}).status_code == 200
    assert _detail(client, auth_headers, wf_id)["name"] == "阿尔法2"

    # tool_call_name 唯一：重名 422
    assert client.post("/api/workflows", headers=auth_headers, json={
        "name": "x", "tool_call_name": "wf_alpha", "description": "d",
    }).status_code == 422
    # tool_call_name 非法标识符（数字开头）→ 422（schema 正则）
    assert client.post("/api/workflows", headers=auth_headers, json={
        "name": "x", "tool_call_name": "9bad", "description": "d",
    }).status_code == 422

    # 归属隔离：他人看不到 / 改不了 / 删不了（403）
    assert client.get(f"/api/workflows/{wf_id}", headers=other_headers).status_code == 403
    assert client.post(f"/api/workflows/{wf_id}", headers=other_headers,
                       json={"name": "黑客"}).status_code == 403
    assert client.post(f"/api/workflows/{wf_id}/delete", headers=other_headers).status_code == 403

    # 自己删
    assert client.post(f"/api/workflows/{wf_id}/delete", headers=auth_headers).status_code == 200
    assert client.get(f"/api/workflows/{wf_id}", headers=auth_headers).status_code == 404


# ---------------- 草稿图保存 / 读取 ----------------

def test_draft_graph_save_get(client, auth_headers):
    wf_id = _create(client, auth_headers, "wf_draft")
    nodes, edges = _minimal_graph()
    _save_draft(client, auth_headers, wf_id, nodes, edges)

    graph = client.get(f"/api/workflows/{wf_id}/draft-graph", headers=auth_headers).get_json()["data"]
    assert len(graph["nodes"]) == 3 and len(graph["edges"]) == 2
    assert {n["node_type"] for n in graph["nodes"]} == {"start", "template_transform", "end"}
    # 存草稿即重置调试通过标记
    assert _detail(client, auth_headers, wf_id)["is_debug_passed"] is False
    assert _detail(client, auth_headers, wf_id)["node_count"] == 3


# ---------------- 发布闸门：未调试通过不可发布 ----------------

def test_publish_requires_debug_passed(client, auth_headers):
    wf_id = _create(client, auth_headers, "wf_pub_gate")
    nodes, edges = _minimal_graph()
    _save_draft(client, auth_headers, wf_id, nodes, edges)
    # 未调试通过 → 发布 422
    assert client.post(f"/api/workflows/{wf_id}/publish", headers=auth_headers).status_code == 422


# ---------------- 调试(SSE) → 发布 → 取消发布 全链路 ----------------

def test_debug_then_publish_then_cancel(client, auth_headers):
    wf_id = _create(client, auth_headers, "wf_run")
    nodes, edges = _minimal_graph()
    _save_draft(client, auth_headers, wf_id, nodes, edges)

    # 调试：SSE 逐节点 workflow 帧
    r = client.post(f"/api/workflows/{wf_id}/debug", headers=auth_headers, json={"name": "世界"})
    assert r.status_code == 200, r.get_data(as_text=True)
    events = _sse_events(r.get_data(as_text=True))
    assert "workflow" in events and "error" not in events

    # 跑通后发布闸门点亮
    assert _detail(client, auth_headers, wf_id)["is_debug_passed"] is True

    # 发布成功 → status published；发布会再次复位 is_debug_passed
    assert client.post(f"/api/workflows/{wf_id}/publish", headers=auth_headers).status_code == 200
    assert _detail(client, auth_headers, wf_id)["status"] == "published"

    # 取消发布 → 回 draft
    assert client.post(f"/api/workflows/{wf_id}/cancel-publish", headers=auth_headers).status_code == 200
    assert _detail(client, auth_headers, wf_id)["status"] == "draft"
    # 未发布再取消 → 422
    assert client.post(f"/api/workflows/{wf_id}/cancel-publish", headers=auth_headers).status_code == 422


# ---------------- 配额：每用户工作流数上限（默认 3）----------------

def test_quota_max_workflows(client, auth_headers):
    for i in range(3):
        _create(client, auth_headers, f"wf_q{i}")
    # 第 4 个 → 422（QUOTA_MAX_WORKFLOWS_PER_USER 默认 3）
    assert client.post("/api/workflows", headers=auth_headers, json={
        "name": "x", "tool_call_name": "wf_q_over", "description": "d",
    }).status_code == 422


# ---------------- 决策①：代码节点对所有登录用户开放 ----------------

def test_code_node_open_to_all_users(client, auth_headers):
    """本平台无管理员（is_admin 恒 False），但工作流校验按 is_admin=True 放行，
    故代码节点对所有登录用户可用——存草稿后代码节点不被剔除。"""
    wf_id = _create(client, auth_headers, "wf_code")
    start = _start(inputs=[_input_var("x")])
    code = {"id": _nid(), "node_type": "code", "title": "代码",
            "code": "def main(params):\n    return params"}
    end = _end()
    nodes = [start, code, end]
    edges = [_edge(start, code), _edge(code, end)]
    _save_draft(client, auth_headers, wf_id, nodes, edges)

    graph = client.get(f"/api/workflows/{wf_id}/draft-graph", headers=auth_headers).get_json()["data"]
    assert "code" in {n["node_type"] for n in graph["nodes"]}  # 未被剔除 = 已对所有用户开放


# ---------------- 决策②：已发布工作流可解析为 chat 工具（应用内调用底座）----------------

def test_published_workflow_resolves_as_langchain_tool(client, app, make_account, make_token):
    from internal.extension.database_extension import db
    from internal.model import Account
    from internal.service import WorkflowService
    from app.http.module import injector

    aid = make_account()
    other_id = make_account()
    headers = {"Authorization": f"Bearer {make_token(aid)}"}

    wf_id = _create(client, headers, "wf_tool")
    nodes, edges = _minimal_graph()
    _save_draft(client, headers, wf_id, nodes, edges)
    # 必须读完调试的 SSE 流（stream_with_context 否则会把请求上下文留在栈上，污染下个请求）
    dbg = client.post(f"/api/workflows/{wf_id}/debug", headers=headers, json={"name": "x"})
    assert "workflow" in _sse_events(dbg.get_data(as_text=True))
    assert client.post(f"/api/workflows/{wf_id}/publish", headers=headers).status_code == 200

    with app.app_context():
        svc = injector.get(WorkflowService)
        owner = db.session.get(Account, aid)
        other = db.session.get(Account, other_id)
        # 本人 + 已发布 → 解析出 1 个工作流工具
        assert len(svc.get_langchain_tools_by_ids([wf_id], owner)) == 1
        # 他人 → 0（归属过滤）
        assert svc.get_langchain_tools_by_ids([wf_id], other) == []
        # 空列表 → 0
        assert svc.get_langchain_tools_by_ids([], owner) == []
