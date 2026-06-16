"""知识库端到端：上传 .txt → 建文档 → 同步跑索引管线 → 命中测试 → 片段 CRUD。

本平台无超管概念（Account.is_admin 恒 False），配额已拍平：所有登录用户走同一套可配置配额（<=0=不限）。

本机沙箱无 redis/Qdrant：
- 纯 DB/请求维度（上传、知识库 CRUD、建文档→waiting、归属隔离、DB 维度配额）本机即可跑；
- 触 Qdrant（索引/命中/片段向量）或 redis（关键词倒排锁、限流计数）的用例用
  qdrant_client_or_skip / redis_or_skip 守卫，本机跳过、交 CI（有 service 容器）。
fake_embeddings（8 维确定性假向量，query==片段文本时 cosine=1）+ kb_collection（独立 Qdrant collection）
+ no_celery_dispatch（异步任务 .delay no-op，改为直接同步调 IndexingService）。
"""
import io

import pytest

CONTENT = "测试知识库内容：人工智能让生活更美好。"


@pytest.fixture(autouse=True)
def _tmp_storage(app, tmp_path, monkeypatch):
    """把上传落盘根目录指向 pytest 临时目录，避免污染工作区。"""
    monkeypatch.setitem(app.config, "STORAGE_ROOT", str(tmp_path))


def _upload_txt(client, headers, text=CONTENT, filename="kb.txt"):
    data = {"file": (io.BytesIO(text.encode("utf-8")), filename)}
    r = client.post("/api/upload-files/file", headers=headers, data=data, content_type="multipart/form-data")
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()["data"]["id"]


def _create_dataset(client, headers, name="kb-e2e"):
    r = client.post("/api/datasets", headers=headers, json={"name": name})
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()["data"]["id"]


def _create_doc(client, headers, ds_id, fid):
    """直接 POST 建文档，不断言成功（用于检查超限被拒）。返回 Response。"""
    return client.post(f"/api/datasets/{ds_id}/documents", headers=headers,
                       json={"upload_file_ids": [fid], "process_type": "automatic"})


def _run_indexing(app, document_ids):
    from app.http.module import injector
    from internal.service import IndexingService
    with app.app_context():
        injector.get(IndexingService).build_documents(document_ids)


# ---------- 上传（本机可跑） ----------

def test_upload_txt(client, auth_headers):
    fid = _upload_txt(client, auth_headers)
    assert isinstance(fid, int) and fid > 0


def test_upload_rejects_unsupported_ext(client, auth_headers):
    data = {"file": (io.BytesIO(b"x"), "bad.exe")}
    r = client.post("/api/upload-files/file", headers=auth_headers, data=data, content_type="multipart/form-data")
    assert r.status_code == 422


# ---------- 知识库 CRUD + 建文档（本机可跑：建文档停在 waiting，不触 Qdrant/redis） ----------

def test_dataset_crud(client, auth_headers, no_celery_dispatch):
    ds_id = _create_dataset(client, auth_headers, name="kb-crud")
    # 详情
    ds = client.get(f"/api/datasets/{ds_id}", headers=auth_headers).get_json()["data"]
    assert ds["name"] == "kb-crud" and ds["document_count"] == 0
    # 列表
    lst = client.get("/api/datasets", headers=auth_headers).get_json()["data"]["list"]
    assert any(d["id"] == ds_id for d in lst)
    # 改名
    assert client.post(f"/api/datasets/{ds_id}", headers=auth_headers,
                       json={"name": "kb-crud-2"}).status_code == 200
    assert client.get(f"/api/datasets/{ds_id}", headers=auth_headers).get_json()["data"]["name"] == "kb-crud-2"
    # 删除（异步清向量被 no-op）
    assert client.post(f"/api/datasets/{ds_id}/delete", headers=auth_headers).status_code == 200
    assert client.get(f"/api/datasets/{ds_id}", headers=auth_headers).status_code == 404


def test_create_documents_waiting(client, auth_headers, no_celery_dispatch):
    ds_id = _create_dataset(client, auth_headers, name="kb-doc-waiting")
    fid = _upload_txt(client, auth_headers)
    r = _create_doc(client, auth_headers, ds_id, fid)
    assert r.status_code == 200, r.get_data(as_text=True)
    payload = r.get_json()["data"]
    assert payload["batch"]
    assert payload["documents"][0]["status"] == "waiting"


def test_dataset_isolation_across_users(client, auth_headers, other_headers):
    """跨用户归属隔离：A 的知识库 B 看不到（404），列表也互不可见。"""
    ds_id = _create_dataset(client, auth_headers, name="kb-iso")
    assert client.get(f"/api/datasets/{ds_id}", headers=other_headers).status_code == 404
    lst = client.get("/api/datasets", headers=other_headers).get_json()["data"]["list"]
    assert all(d["id"] != ds_id for d in lst)


def test_create_documents_rejects_foreign_upload_file(client, auth_headers, other_headers):
    """上传文件归属校验：用别人的 upload_file_id 建文档应被拒（无有效文件）。"""
    ds_id = _create_dataset(client, auth_headers, name="kb-x")
    foreign_fid = _upload_txt(client, other_headers)  # 属于另一个账号
    r = _create_doc(client, auth_headers, ds_id, foreign_fid)
    assert r.status_code == 422


def test_reindex_rejected_while_processing(client, auth_headers, no_celery_dispatch):
    """非终态（waiting/处理中）文档不允许重新索引。"""
    ds_id = _create_dataset(client, auth_headers, name="kb-reindex-busy")
    fid = _upload_txt(client, auth_headers)
    doc_id = _create_doc(client, auth_headers, ds_id, fid).get_json()["data"]["documents"][0]["id"]  # 停在 waiting
    r = client.post(f"/api/datasets/{ds_id}/documents/{doc_id}/re-index", headers=auth_headers)
    assert r.status_code == 422


def test_recover_stuck_documents(app, client, auth_headers, no_celery_dispatch):
    """卡在中间态且超阈值的文档被启动恢复钩子复位为 error（纯 DB，不触 Qdrant）。"""
    from datetime import datetime, timedelta
    from app.http.module import injector
    from internal.extension.database_extension import db
    from internal.model import Document
    from internal.service import IndexingService

    ds_id = _create_dataset(client, auth_headers, name="kb-stuck")
    fid = _upload_txt(client, auth_headers)
    doc_id = _create_doc(client, auth_headers, ds_id, fid).get_json()["data"]["documents"][0]["id"]

    # 模拟「worker 被杀、任务丢失」：手动卡在 indexing 且开始时间在阈值之前
    with app.app_context():
        with db.auto_commit():
            doc = db.session.get(Document, doc_id)
            doc.status = "indexing"
            doc.processing_started_at = datetime.utcnow() - timedelta(hours=1)
        recovered = injector.get(IndexingService).recover_stuck_documents()
    assert recovered >= 1

    doc = client.get(f"/api/datasets/{ds_id}/documents/{doc_id}", headers=auth_headers).get_json()["data"]
    assert doc["status"] == "error" and doc["error"]


# ---------- DB 维度配额（本机可跑：拍平后所有登录用户统一受限） ----------

def test_quota_dataset_limit(app, client, auth_headers, monkeypatch):
    """建知识库数量到上限即被拒（无超管豁免）。"""
    monkeypatch.setitem(app.config, "QUOTA_MAX_DATASETS_PER_USER", 2)
    _create_dataset(client, auth_headers, name="q-ds-1")
    _create_dataset(client, auth_headers, name="q-ds-2")
    r = client.post("/api/datasets", headers=auth_headers, json={"name": "q-ds-3"})
    assert r.status_code == 422


def test_quota_upload_size(app, client, auth_headers, monkeypatch):
    """单文件超过 QUOTA_USER_UPLOAD_MAX_SIZE 被拒（无超管豁免）。"""
    monkeypatch.setitem(app.config, "QUOTA_USER_UPLOAD_MAX_SIZE", 10)  # 10 字节，CONTENT 远超
    data = {"file": (io.BytesIO(CONTENT.encode("utf-8")), "kb.txt")}
    r = client.post("/api/upload-files/file", headers=auth_headers, data=data,
                    content_type="multipart/form-data")
    assert r.status_code == 422


def test_quota_doc_per_dataset_limit(app, client, auth_headers, no_celery_dispatch, monkeypatch):
    """单个知识库文档数到上限即被拒（与灌库冷却/日次数解耦，纯 DB 计数）。"""
    monkeypatch.setitem(app.config, "QUOTA_MAX_DOCS_PER_DATASET", 1)
    monkeypatch.setitem(app.config, "QUOTA_BUILD_COOLDOWN_SECONDS", 0)
    monkeypatch.setitem(app.config, "QUOTA_BUILD_DAILY_LIMIT", 0)  # 关日次数，单测每库上限

    ds_id = _create_dataset(client, auth_headers, name="q-doc-cap")
    f1 = _upload_txt(client, auth_headers)
    f2 = _upload_txt(client, auth_headers)
    assert _create_doc(client, auth_headers, ds_id, f1).status_code == 200  # 第 1 篇
    assert _create_doc(client, auth_headers, ds_id, f2).status_code == 422  # 超每库上限


# ====================== 以下需 Qdrant + redis：本机跳过，交 CI ======================

def test_full_pipeline_index_and_hit(app, client, auth_headers, fake_embeddings, kb_collection,
                                     no_celery_dispatch, qdrant_client_or_skip, redis_or_skip):
    ds_id = _create_dataset(client, auth_headers)
    fid = _upload_txt(client, auth_headers)

    r = _create_doc(client, auth_headers, ds_id, fid)
    assert r.status_code == 200, r.get_data(as_text=True)
    payload = r.get_json()["data"]
    batch = payload["batch"]
    doc_id = payload["documents"][0]["id"]
    assert payload["documents"][0]["status"] == "waiting"

    # 同步跑索引管线
    _run_indexing(app, [doc_id])

    # 批次状态 → completed
    status = client.get(f"/api/datasets/{ds_id}/documents/batch/{batch}", headers=auth_headers).get_json()["data"]
    assert status[0]["status"] == "completed"
    assert status[0]["segment_count"] >= 1
    assert status[0]["completed_segment_count"] == status[0]["segment_count"]

    # 文档详情：enabled + 有字符数
    doc = client.get(f"/api/datasets/{ds_id}/documents/{doc_id}", headers=auth_headers).get_json()["data"]
    assert doc["status"] == "completed" and doc["enabled"] is True
    assert doc["character_count"] > 0

    # 知识库统计量更新
    dataset = client.get(f"/api/datasets/{ds_id}", headers=auth_headers).get_json()["data"]
    assert dataset["document_count"] == 1
    assert dataset["character_count"] > 0

    # 命中测试（语义）：query == 片段文本 → 命中该片段
    hit = client.post(f"/api/datasets/{ds_id}/hit", headers=auth_headers,
                      json={"query": CONTENT, "retrieval_strategy": "semantic", "k": 4})
    assert hit.status_code == 200, hit.get_data(as_text=True)
    results = hit.get_json()["data"]
    assert len(results) >= 1
    assert CONTENT in results[0]["content"]
    assert results[0]["score"] > 0.9
    assert results[0]["document"]["id"] == doc_id

    # 命中后：查询历史落库 + 片段 hit_count 自增
    queries = client.get(f"/api/datasets/{ds_id}/queries", headers=auth_headers).get_json()["data"]
    assert len(queries) >= 1 and queries[0]["query"] == CONTENT

    segs = client.get(f"/api/datasets/{ds_id}/documents/{doc_id}/segments", headers=auth_headers).get_json()["data"]["list"]
    assert segs[0]["hit_count"] >= 1


def test_segment_crud(app, client, auth_headers, fake_embeddings, kb_collection,
                      no_celery_dispatch, qdrant_client_or_skip, redis_or_skip):
    ds_id = _create_dataset(client, auth_headers, name="kb-seg")
    fid = _upload_txt(client, auth_headers)
    doc_id = _create_doc(client, auth_headers, ds_id, fid).get_json()["data"]["documents"][0]["id"]
    _run_indexing(app, [doc_id])

    base = f"/api/datasets/{ds_id}/documents/{doc_id}/segments"

    # 手动新增片段
    r = client.post(base, headers=auth_headers, json={"content": "新增的片段内容"})
    assert r.status_code == 200, r.get_data(as_text=True)
    seg = r.get_json()["data"]
    seg_id = seg["id"]
    assert seg["enabled"] is True and seg["content"] == "新增的片段内容"

    # 列表能看到
    segs = client.get(base, headers=auth_headers).get_json()["data"]["list"]
    assert any(s["id"] == seg_id for s in segs)

    # 改内容
    r = client.post(f"{base}/{seg_id}", headers=auth_headers, json={"content": "改过的内容"})
    assert r.status_code == 200
    assert client.get(f"{base}/{seg_id}", headers=auth_headers).get_json()["data"]["content"] == "改过的内容"

    # 禁用
    assert client.post(f"{base}/{seg_id}/enabled", headers=auth_headers, json={"enabled": False}).status_code == 200
    assert client.get(f"{base}/{seg_id}", headers=auth_headers).get_json()["data"]["enabled"] is False

    # 删除
    assert client.post(f"{base}/{seg_id}/delete", headers=auth_headers).status_code == 200
    assert client.get(f"{base}/{seg_id}", headers=auth_headers).status_code == 404


def test_reindex_is_idempotent(app, client, auth_headers, fake_embeddings, kb_collection,
                               no_celery_dispatch, qdrant_client_or_skip, redis_or_skip, monkeypatch):
    """重新索引：终态文档可复位重建，且幂等（片段不翻倍、向量重建后仍可命中）。"""
    # 关掉灌库冷却/日次数，单测幂等本身（否则紧接 create 的 reindex 会被冷却拦）
    monkeypatch.setitem(app.config, "QUOTA_BUILD_COOLDOWN_SECONDS", 0)
    monkeypatch.setitem(app.config, "QUOTA_BUILD_DAILY_LIMIT", 100)
    ds_id = _create_dataset(client, auth_headers, name="kb-reindex")
    fid = _upload_txt(client, auth_headers)
    doc_id = _create_doc(client, auth_headers, ds_id, fid).get_json()["data"]["documents"][0]["id"]
    _run_indexing(app, [doc_id])

    segs_url = f"/api/datasets/{ds_id}/documents/{doc_id}/segments"
    n1 = len(client.get(segs_url, headers=auth_headers).get_json()["data"]["list"])
    assert n1 >= 1

    # 重新索引（.delay 被 no-op → 文档复位 waiting，再手动跑管线）
    r = client.post(f"/api/datasets/{ds_id}/documents/{doc_id}/re-index", headers=auth_headers)
    assert r.status_code == 200, r.get_data(as_text=True)
    doc = client.get(f"/api/datasets/{ds_id}/documents/{doc_id}", headers=auth_headers).get_json()["data"]
    assert doc["status"] == "waiting" and doc["error"] in (None, "")
    _run_indexing(app, [doc_id])

    # 幂等：片段数不变（无重复），文档回到 completed+enabled
    doc = client.get(f"/api/datasets/{ds_id}/documents/{doc_id}", headers=auth_headers).get_json()["data"]
    assert doc["status"] == "completed" and doc["enabled"] is True
    assert len(client.get(segs_url, headers=auth_headers).get_json()["data"]["list"]) == n1

    # 向量已重建，命中测试仍能命中
    hit = client.post(f"/api/datasets/{ds_id}/hit", headers=auth_headers,
                      json={"query": CONTENT, "retrieval_strategy": "semantic", "k": 4})
    results = hit.get_json()["data"]
    assert len(results) >= 1 and results[0]["score"] > 0.9


def test_quota_hit_rate_limit(app, client, auth_headers, fake_embeddings, kb_collection,
                              no_celery_dispatch, qdrant_client_or_skip, redis_or_skip, monkeypatch):
    """命中检索每分钟到上限被拒（先灌好一篇文档使知识库可检索）。"""
    monkeypatch.setitem(app.config, "QUOTA_HIT_PER_MINUTE", 2)
    monkeypatch.setitem(app.config, "QUOTA_HIT_DAILY_LIMIT", 100)
    monkeypatch.setitem(app.config, "QUOTA_BUILD_COOLDOWN_SECONDS", 0)
    monkeypatch.setitem(app.config, "QUOTA_BUILD_DAILY_LIMIT", 100)

    ds_id = _create_dataset(client, auth_headers, name="q-hit")
    fid = _upload_txt(client, auth_headers)
    doc_id = _create_doc(client, auth_headers, ds_id, fid).get_json()["data"]["documents"][0]["id"]
    _run_indexing(app, [doc_id])

    body = {"query": CONTENT, "retrieval_strategy": "semantic", "k": 4}
    assert client.post(f"/api/datasets/{ds_id}/hit", headers=auth_headers, json=body).status_code == 200
    assert client.post(f"/api/datasets/{ds_id}/hit", headers=auth_headers, json=body).status_code == 200
    assert client.post(f"/api/datasets/{ds_id}/hit", headers=auth_headers, json=body).status_code == 422  # 超每分钟


def test_quota_build_cooldown(app, client, auth_headers, no_celery_dispatch, redis_or_skip, monkeypatch):
    """两次灌库之间有冷却：紧接着的第二次被拒（redis 计数）。"""
    monkeypatch.setitem(app.config, "QUOTA_BUILD_COOLDOWN_SECONDS", 600)
    monkeypatch.setitem(app.config, "QUOTA_BUILD_DAILY_LIMIT", 100)
    monkeypatch.setitem(app.config, "QUOTA_MAX_DOCS_PER_DATASET", 100)

    ds_id = _create_dataset(client, auth_headers, name="q-cooldown")
    f1 = _upload_txt(client, auth_headers)
    f2 = _upload_txt(client, auth_headers)
    assert _create_doc(client, auth_headers, ds_id, f1).status_code == 200  # 记一次灌库 → 进冷却
    assert _create_doc(client, auth_headers, ds_id, f2).status_code == 422  # 冷却中被拒


def test_quota_build_daily_limit(app, client, auth_headers, no_celery_dispatch, redis_or_skip, monkeypatch):
    """每日灌库次数到上限被拒（redis 计数）。"""
    monkeypatch.setitem(app.config, "QUOTA_BUILD_COOLDOWN_SECONDS", 0)  # 关冷却，单测日次数
    monkeypatch.setitem(app.config, "QUOTA_BUILD_DAILY_LIMIT", 1)
    monkeypatch.setitem(app.config, "QUOTA_MAX_DOCS_PER_DATASET", 100)

    ds_id = _create_dataset(client, auth_headers, name="q-daily")
    f1 = _upload_txt(client, auth_headers)
    f2 = _upload_txt(client, auth_headers)
    assert _create_doc(client, auth_headers, ds_id, f1).status_code == 200  # 当日第 1 次
    assert _create_doc(client, auth_headers, ds_id, f2).status_code == 422  # 超当日上限
