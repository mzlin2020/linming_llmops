"""Phase 4b：App + 草稿/发布配置 + 公共应用商店 + 会话 + Chat(SSE) + AI 辅助 + 辅助 Agent。

本机可跑（DB/请求维度 + fake_llm 裸 LLM 流，不连 redis/Qdrant/真实模型）。
Agent/工具路径（run_agent_stream 触 redis register_task）、RAG-in-chat 真 Qdrant 全链路交 CI。
"""
import json

import pytest


# ---------------- helpers ----------------

def _create_app(client, headers, name="app-x", preset=None):
    body = {"name": name}
    if preset is not None:
        body["preset_prompt"] = preset
    r = client.post("/api/apps", headers=headers, json=body)
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()["data"]


def _publish(client, headers, app_id):
    r = client.post(f"/api/apps/{app_id}/publish", headers=headers)
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()["data"]


def _sse_events(text: str) -> list[str]:
    """从 SSE 文本里抽出所有 event 名（按出现顺序）。"""
    return [ln.split("event: ", 1)[1] for ln in text.splitlines() if ln.startswith("event: ")]


# ---------------- App CRUD ----------------

def test_app_crud(client, auth_headers):
    app = _create_app(client, auth_headers, "crud-app", preset="你是助手")
    app_id = app["id"]
    assert app["name"] == "crud-app"
    assert app["status"] == "draft"
    # 详情含 app_config 全集 + is_public
    detail = client.get(f"/api/apps/{app_id}", headers=auth_headers).get_json()["data"]
    assert detail["preset_prompt"] == "你是助手"
    assert "app_config" in detail and detail["is_public"] is False
    # 默认草稿挂了 current_time 工具（开箱即可验证工具链路），且只含通用零依赖工具、无厂商专有工具
    tools = detail["app_config"]["tools"]
    assert any(t["tool"]["name"] == "current_time" for t in tools)
    # 更新
    assert client.post(f"/api/apps/{app_id}", headers=auth_headers,
                       json={"name": "crud-app-2"}).status_code == 200
    assert client.get(f"/api/apps/{app_id}", headers=auth_headers).get_json()["data"]["name"] == "crud-app-2"
    # 列表只含自己的
    lst = client.get("/api/apps", headers=auth_headers).get_json()["data"]
    assert any(a["id"] == app_id for a in lst)
    # 复制
    copy = client.post(f"/api/apps/{app_id}/copy", headers=auth_headers).get_json()["data"]
    assert copy["id"] != app_id and "副本" in copy["name"]
    # 删除
    assert client.post(f"/api/apps/{app_id}/delete", headers=auth_headers).status_code == 200
    assert client.get(f"/api/apps/{app_id}", headers=auth_headers).status_code == 404


def test_app_default_auto_create(client, auth_headers):
    a = client.get("/api/apps/default", headers=auth_headers).get_json()["data"]
    assert a["is_default"] is True
    # 再取一次是同一个（不会重复建）
    b = client.get("/api/apps/default", headers=auth_headers).get_json()["data"]
    assert a["id"] == b["id"]


def test_app_cross_user_forbidden(client, auth_headers, other_headers):
    app_id = _create_app(client, auth_headers, "owned")["id"]
    assert client.get(f"/api/apps/{app_id}", headers=other_headers).status_code == 403


# ---------------- 草稿配置校验 / 发布 / 历史 / 回退 ----------------

def test_draft_config_validate_and_publish(client, auth_headers):
    app_id = _create_app(client, auth_headers, "cfg-app")["id"]
    # 合法更新：dialog_round 钳制、合法 builtin 工具
    r = client.post(f"/api/apps/{app_id}/draft-app-config", headers=auth_headers, json={
        "dialog_round": 999,  # 钳到 100
        "preset_prompt": "人设",
        "tools": [{"type": "builtin_tool", "provider": {"name": "time"},
                   "tool": {"name": "current_time", "params": {}}}],
    })
    assert r.status_code == 200, r.get_data(as_text=True)
    cfg = r.get_json()["data"]
    assert cfg["dialog_round"] == 100 and cfg["preset_prompt"] == "人设"
    # 非法工具 → 422
    bad = client.post(f"/api/apps/{app_id}/draft-app-config", headers=auth_headers, json={
        "tools": [{"type": "builtin_tool", "provider": {"name": "nope"}, "tool": {"name": "x"}}],
    })
    assert bad.status_code == 422
    # 发布 → status published；published-config 有值；历史 1 条
    pub = _publish(client, auth_headers, app_id)
    assert pub["status"] == "published"
    assert client.get(f"/api/apps/{app_id}/published-config", headers=auth_headers).get_json()["data"]["preset_prompt"] == "人设"
    hist = client.get(f"/api/apps/{app_id}/publish-histories", headers=auth_headers).get_json()["data"]
    assert hist["paginator"]["total_record"] == 1
    version_id = hist["list"][0]["id"]
    # 改草稿再回退到历史版本
    client.post(f"/api/apps/{app_id}/draft-app-config", headers=auth_headers, json={"preset_prompt": "改了"})
    fb = client.post(f"/api/apps/{app_id}/fallback-history", headers=auth_headers,
                     json={"app_config_version_id": version_id})
    assert fb.status_code == 200 and fb.get_json()["data"]["preset_prompt"] == "人设"
    # 取消发布 → 草稿态、published-config 空（None 经 success() 归一为 {}）
    assert client.post(f"/api/apps/{app_id}/cancel-publish", headers=auth_headers).status_code == 200
    assert not client.get(f"/api/apps/{app_id}/published-config", headers=auth_headers).get_json()["data"]


def test_config_dataset_binding_ownership(client, auth_headers, other_headers):
    """datasets 绑定只保留自有库；他人库 id 静默过滤。"""
    app_id = _create_app(client, auth_headers, "ds-bind")["id"]
    mine = client.post("/api/datasets", headers=auth_headers, json={"name": "kb-own"}).get_json()["data"]["id"]
    others = client.post("/api/datasets", headers=other_headers, json={"name": "kb-other"}).get_json()["data"]["id"]
    cfg = client.post(f"/api/apps/{app_id}/draft-app-config", headers=auth_headers,
                      json={"datasets": [mine, others]}).get_json()["data"]
    assert cfg["datasets"] == [mine]  # 他人库被剔除


# ---------------- 应用市场（拍平：仅登录可发布自有已发布应用）----------------

def test_app_store_flatten_publish_and_add(client, auth_headers, other_headers):
    app_id = _create_app(client, auth_headers, "store-app", preset="商店人设")["id"]
    # 未发布不能上架 → 422
    assert client.post(f"/api/apps/{app_id}/store-publish", headers=auth_headers,
                       json={"is_public": True}).status_code == 422
    _publish(client, auth_headers, app_id)
    # 普通登录用户（is_admin 恒 False）即可上架自有已发布应用 → 拍平生效
    assert client.post(f"/api/apps/{app_id}/store-publish", headers=auth_headers,
                       json={"is_public": True}).status_code == 200
    # 商店列表可见
    store = client.get("/api/app-store", headers=other_headers).get_json()["data"]["list"]
    pub = next(p for p in store if p["name"] == "store-app")
    assert pub["added"] is False
    # 他人添加到自己列表
    added = client.post(f"/api/app-store/{pub['id']}/add", headers=other_headers)
    assert added.status_code == 200
    new_app_id = added.get_json()["data"]["id"]
    assert new_app_id != app_id
    # 添加后商店标记 added=True；重复添加 422
    store2 = client.get("/api/app-store", headers=other_headers).get_json()["data"]["list"]
    assert next(p for p in store2 if p["id"] == pub["id"])["added"] is True
    assert client.post(f"/api/app-store/{pub['id']}/add", headers=other_headers).status_code == 422


def test_app_store_publish_only_own_app(client, auth_headers, other_headers):
    app_id = _create_app(client, auth_headers, "not-yours")["id"]
    _publish(client, auth_headers, app_id)
    # 他人不能把不属于自己的应用上架 → 404（不泄露存在性）
    assert client.post(f"/api/apps/{app_id}/store-publish", headers=other_headers,
                       json={"is_public": True}).status_code == 404


# ---------------- 会话 CRUD ----------------

def test_conversation_crud_and_isolation(client, auth_headers, other_headers, fake_llm, no_after_round_dispatch):
    app_id = _create_app(client, auth_headers, "conv-app")["id"]
    # 先聊一轮，产生一个会话 + 一条消息
    client.post(f"/api/apps/{app_id}/conversations/complete", headers=auth_headers, json={"query": "hi"})
    convs = client.get("/api/conversations", headers=auth_headers).get_json()["data"]
    assert len(convs) == 1
    conv_id = convs[0]["id"]
    # 改名 / 置顶
    assert client.post(f"/api/conversations/{conv_id}/name", headers=auth_headers,
                       json={"name": "我的会话"}).status_code == 200
    assert client.get(f"/api/conversations/{conv_id}/name", headers=auth_headers).get_json()["data"]["name"] == "我的会话"
    assert client.post(f"/api/conversations/{conv_id}/is-pinned", headers=auth_headers,
                       json={"is_pinned": True}).status_code == 200
    # 消息分页
    page = client.get(f"/api/conversations/{conv_id}/messages", headers=auth_headers).get_json()["data"]
    assert page["paginator"]["total_record"] == 1
    # 跨用户隔离
    assert client.get(f"/api/conversations/{conv_id}", headers=other_headers).status_code == 403
    # 删除
    assert client.post(f"/api/conversations/{conv_id}/delete", headers=auth_headers).status_code == 200
    assert client.get(f"/api/conversations/{conv_id}", headers=auth_headers).status_code == 404


# ---------------- Chat（裸 LLM：fake_llm + 无工具）----------------

def test_debug_chat_sse_and_persist(client, auth_headers, fake_llm, no_after_round_dispatch):
    app_id = _create_app(client, auth_headers, "chat-app")["id"]
    r = client.post(f"/api/apps/{app_id}/conversations", headers=auth_headers, json={"query": "你好"})
    assert r.status_code == 200
    text = r.get_data(as_text=True)
    events = _sse_events(text)
    assert events[0] == "ping" and "message" in events and events[-1] == "agent_end"
    assert "这是来自" in text  # delta 帧带回答内容（回答按 4 字一块流式下发，整句完整性由下方落库断言验证）
    # 消息落库：answer = fake 回复
    msgs = client.get(f"/api/apps/{app_id}/conversations/messages", headers=auth_headers).get_json()["data"]["list"]
    assert len(msgs) == 1 and msgs[0]["answer"].startswith("这是来自假模型")
    assert msgs[0]["status"] == "normal"


def test_complete_chat_sync(client, auth_headers, fake_llm, no_after_round_dispatch):
    app_id = _create_app(client, auth_headers, "sync-app")["id"]
    r = client.post(f"/api/apps/{app_id}/conversations/complete", headers=auth_headers, json={"query": "q"})
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert data["answer"].startswith("这是来自假模型") and data["status"] == "normal"


def test_published_chat_silo_separation(client, auth_headers, fake_llm, no_after_round_dispatch):
    """调试会话(草稿) 与 已发布对话 是两个独立 silo。"""
    app_id = _create_app(client, auth_headers, "silo-app", preset="发布人设")["id"]
    # 未发布时走 published 链路 → 422
    assert client.post(f"/api/apps/{app_id}/published-conversations/complete", headers=auth_headers,
                       json={"query": "x"}).status_code == 422
    _publish(client, auth_headers, app_id)
    # debug 一轮 + published 一轮
    client.post(f"/api/apps/{app_id}/conversations/complete", headers=auth_headers, json={"query": "debug 轮"})
    client.post(f"/api/apps/{app_id}/published-conversations/complete", headers=auth_headers, json={"query": "published 轮"})
    debug_msgs = client.get(f"/api/apps/{app_id}/conversations/messages", headers=auth_headers).get_json()["data"]["list"]
    pub_msgs = client.get(f"/api/apps/{app_id}/published-conversations/messages", headers=auth_headers).get_json()["data"]["list"]
    assert [m["query"] for m in debug_msgs] == ["debug 轮"]
    assert [m["query"] for m in pub_msgs] == ["published 轮"]
    # 清空已发布历史只抹消息
    assert client.post(f"/api/apps/{app_id}/published-conversations/clear", headers=auth_headers).status_code == 200
    assert client.get(f"/api/apps/{app_id}/published-conversations/messages", headers=auth_headers).get_json()["data"]["paginator"]["total_record"] == 0


# ---------------- AI 辅助 ----------------

def test_ai_optimize_and_suggest(client, auth_headers, fake_llm, no_after_round_dispatch):
    # 优化人设 → 返回 fake 文本
    r = client.post("/api/ai/optimize-preset-prompt", headers=auth_headers, json={"prompt": "原始人设"})
    assert r.status_code == 200 and r.get_json()["data"]["prompt"].startswith("这是来自假模型")
    # 据消息生成 follow-up：先聊一轮拿 message_id
    app_id = _create_app(client, auth_headers, "ai-app")["id"]
    chat = client.post(f"/api/apps/{app_id}/conversations/complete", headers=auth_headers,
                       json={"query": "q"}).get_json()["data"]
    msg_id = chat["message_id"]
    # fake 回复非 JSON 数组 → 容错解析回 []（不报错）
    sg = client.post("/api/ai/suggested-questions", headers=auth_headers, json={"message_id": msg_id})
    assert sg.status_code == 200 and isinstance(sg.get_json()["data"], list)


def test_ai_suggest_questions_cross_user(client, auth_headers, other_headers, fake_llm, no_after_round_dispatch):
    app_id = _create_app(client, auth_headers, "ai-auth")["id"]
    chat = client.post(f"/api/apps/{app_id}/conversations/complete", headers=auth_headers,
                       json={"query": "q"}).get_json()["data"]
    # 他人不能据我的消息生成 → 403
    assert client.post("/api/ai/suggested-questions", headers=other_headers,
                       json={"message_id": chat["message_id"]}).status_code == 403


# ---------------- after_round（自动命名 + 长期记忆摘要）----------------

def test_after_round_names_and_summarizes(app, client, auth_headers, fake_llm, no_after_round_dispatch):
    from app.http.module import injector
    from internal.extension.database_extension import db
    from internal.model import Conversation
    from internal.service import ConversationService

    app_id = _create_app(client, auth_headers, "round-app")["id"]
    chat = client.post(f"/api/apps/{app_id}/conversations/complete", headers=auth_headers,
                       json={"query": "首问"}).get_json()["data"]
    conv_id, msg_id = chat["conversation_id"], chat["message_id"]
    with app.app_context():
        conv = db.session.get(Conversation, conv_id)
        assert conv.title == "新会话" and not conv.summary  # 收尾被 no-op，尚未命名/摘要
        injector.get(ConversationService).after_round(
            msg_id, provider=None, model=None, long_term_memory_enabled=True,
        )
        db.session.expire_all()
        conv = db.session.get(Conversation, conv_id)
        assert conv.title != "新会话"        # 自动命名生效（fake 文本）
        assert conv.summary                  # 长期记忆摘要生效


# ---------------- 辅助 Agent（全局单例 + 裸 LLM SSE）----------------

def test_assistant_agent_chat(client, auth_headers, fake_llm, no_after_round_dispatch):
    r = client.post("/api/assistant-agent/chat", headers=auth_headers, json={"query": "在吗"})
    assert r.status_code == 200
    events = _sse_events(r.get_data(as_text=True))
    assert events[0] == "ping" and "message" in events and events[-1] == "agent_end"
    # 历史可分页拉到本轮
    msgs = client.get("/api/assistant-agent/messages", headers=auth_headers).get_json()["data"]["list"]
    assert len(msgs) == 1
    # 全局内置助手 app 不混入用户应用列表（user_id=NULL）
    apps = client.get("/api/apps", headers=auth_headers).get_json()["data"]
    assert all(not a.get("is_assistant_agent") for a in apps)
    # 清空会话
    assert client.post("/api/assistant-agent/delete-conversation", headers=auth_headers).status_code == 200
    assert client.get("/api/assistant-agent/messages", headers=auth_headers).get_json()["data"]["paginator"]["total_record"] == 0
