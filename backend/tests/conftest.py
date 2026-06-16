import itertools
import os
import sqlite3
import time

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """本机用 SQLite 代跑时开启 FK 强制，使 ON DELETE CASCADE 生效（MySQL/InnoDB 原生强制）。
    对 MySQL 连接是 no-op。"""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


@pytest.fixture(scope="session")
def app():
    """构建真实 Flask app（不连 DB）。不在此压入 app_context——
    每个 test_client 请求各自压入独立上下文，避免 Flask-Login 的 g._login_user 跨请求缓存。"""
    os.environ.setdefault("JWT_SECRET", "test-secret-please-change")
    from app.http.app import app as flask_app

    flask_app.config["TESTING"] = True
    flask_app.config["PROPAGATE_EXCEPTIONS"] = False
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def app_context(app):
    """供需要 current_app 的纯单元测试使用（如 JwtService）。"""
    with app.app_context():
        yield app


@pytest.fixture(scope="session")
def db_tables(app):
    """建表（连真实 MySQL）。本机无 DB 时依赖此夹具的测试会报错，交给 CI 覆盖。"""
    from internal.extension.database_extension import db

    with app.app_context():
        db.create_all()
    yield
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def make_token(app):
    """直接用 PyJWT 造令牌，便于测试过期/类型错等边界（读 app.config 无需活动上下文）。"""
    import jwt as pyjwt

    secret = app.config["JWT_SECRET"]
    alg = app.config.get("JWT_ALGORITHM", "HS256")

    def _make(account_id, *, type_="access", expired=False, email="u@test.local"):
        now = int(time.time())
        payload = {
            "sub": str(account_id),
            "type": type_,
            "email": email,
            "iat": now - 3600 if expired else now,
            "exp": now - 60 if expired else now + 3600,
        }
        return pyjwt.encode(payload, secret, algorithm=alg)

    return _make


@pytest.fixture
def make_account(app, db_tables):
    """工厂：建真实 Account 行，返回其 id。teardown 统一删除（供后续 handler 测试复用）。"""
    from internal.extension.database_extension import db
    from internal.model import Account
    from pkg.password import hash_password

    created_ids = []
    counter = itertools.count(1)

    def _make(email=None, password="pass1234", name="Tester"):
        email = email or f"user{next(counter)}@test.local"
        with app.app_context():
            acc = Account(email=email, password_hash=hash_password(password), name=name)
            with db.auto_commit():
                db.session.add(acc)
            created_ids.append(acc.id)
            return acc.id

    yield _make

    with app.app_context():
        if created_ids:
            # ai_* 与 account 无外键（认证解耦），SQLite 删账号后自增 id 会被复用，
            # 残留业务行会挂到复用 id 的新账号上污染下个用例。故先清掉这些账号名下所有业务行：
            # 自动发现所有带 user_id 列的表（无需随新增模型手工维护清单），按 FK 依赖逆序（子表先删）。
            for table in reversed(db.metadata.sorted_tables):
                if "user_id" in table.columns:
                    db.session.execute(table.delete().where(table.c.user_id.in_(created_ids)))
            db.session.query(Account).filter(Account.id.in_(created_ids)).delete(synchronize_session=False)
            db.session.commit()


@pytest.fixture
def account(make_account):
    """单个真实 Account 行，返回其 id。"""
    return make_account()


# ====================== Phase 4：handler 集成测试共享夹具 ======================

@pytest.fixture
def auth_headers(make_account, make_token):
    """登录态 Bearer 头：建一个真实 Account，签发其 access JWT。"""
    aid = make_account()
    return {"Authorization": f"Bearer {make_token(aid)}"}


@pytest.fixture
def other_headers(make_account, make_token):
    """第二个、与 auth_headers 不同的账号（用于跨用户归属隔离测试）。"""
    aid = make_account()
    return {"Authorization": f"Bearer {make_token(aid)}"}


@pytest.fixture
def no_celery_dispatch(monkeypatch):
    """把知识库相关 Celery 任务的 .delay 置为 no-op：建文档/重索引/删除后不真正异步派发，
    改由测试显式同步调用 IndexingService 跑管线（与原异步流程解耦，便于断言中间态）。"""
    from internal.task import dataset_task, document_task

    for task in (
        document_task.build_documents,
        document_task.update_document_enabled,
        document_task.delete_document,
        dataset_task.delete_dataset,
    ):
        monkeypatch.setattr(task, "delay", lambda *a, **k: None)
    yield


@pytest.fixture
def redis_or_skip(app):
    """Redis 可用才继续，否则 skip（本机沙箱无 Redis；CI 有 service 容器）。
    知识库灌库/片段维护需要 redis（关键词倒排表用 redis 锁、配额限流用 redis 计数）。"""
    from internal.extension.redis_extension import redis_client

    with app.app_context():
        try:
            redis_client.ping()
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"Redis 不可用，跳过（交 CI 跑）：{exc}")


# ---------------- 知识库（RAG）核心层 + handler 层共享：假 embedding / Qdrant 守卫 ----------------

_FAKE_EMBED_DIM = 8


class _FakeEmbeddings:
    """确定性假 embedding：同一文本→同一向量（query==某片段文本时 cosine=1，命中该片段）。
    维度固定 _FAKE_EMBED_DIM，避免单测加载真实嵌入模型（torch/sentence-transformers）。"""

    @staticmethod
    def _vec(text):
        import hashlib
        digest = hashlib.sha256((text or "").encode("utf-8")).digest()
        return [digest[i % len(digest)] / 255.0 for i in range(_FAKE_EMBED_DIM)]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


@pytest.fixture
def fake_embeddings(monkeypatch):
    """把 EmbeddingsManager.embeddings / vector_size 换成假实现（不加载真实模型）。"""
    from internal.core.embeddings.embeddings_manager import EmbeddingsManager

    fake = _FakeEmbeddings()
    monkeypatch.setattr(EmbeddingsManager, "embeddings", property(lambda self: fake))
    monkeypatch.setattr(EmbeddingsManager, "vector_size", property(lambda self: _FAKE_EMBED_DIM))
    return fake


@pytest.fixture
def qdrant_client_or_skip(app):
    """返回可用的 Qdrant client；连不上则 skip（本机沙箱无 Qdrant，CI 有 service 容器）。"""
    from internal.core.vector_store.qdrant_vector_store import get_qdrant_client

    with app.app_context():
        try:
            client = get_qdrant_client()
            client.get_collections()
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"Qdrant 不可用，跳过（交 CI 跑）：{exc}")
        return client


# ---------------- Chat（4b）：确定性 fake-LLM（不连真实模型/网络） ----------------

class _FakeChatModel:
    """确定性假 chat model：invoke 返回定值 AIMessage、stream 切成几块 AIMessageChunk，
    末块带 usage_metadata（仿 OpenAI stream_usage）。供 chat / ai 辅助 / 收尾命名+摘要单测，
    不加载真实模型、不发网络请求。"""

    def __init__(self, reply: str = "这是来自假模型的回答。", tokens: tuple = (5, 7)):
        self._reply = reply
        self._in, self._out = tokens

    def _usage(self) -> dict:
        return {"input_tokens": self._in, "output_tokens": self._out, "total_tokens": self._in + self._out}

    def invoke(self, messages, **kwargs):
        from langchain_core.messages import AIMessage
        return AIMessage(content=self._reply, usage_metadata=self._usage())

    def stream(self, messages, **kwargs):
        from langchain_core.messages import AIMessageChunk
        parts = [self._reply[i:i + 4] for i in range(0, len(self._reply), 4)] or [""]
        last = len(parts) - 1
        for idx, p in enumerate(parts):
            yield AIMessageChunk(content=p, usage_metadata=self._usage() if idx == last else None)

    def bind_tools(self, tools, **kwargs):
        return self


@pytest.fixture
def fake_llm(monkeypatch):
    """把 LanguageModelManager 的取模型/能力判定换成确定性假实现：
    instantiate / get_default 返回 _FakeChatModel；supports_vision / supports_tool_call 默认 False
    （→ chat 走裸 LLM 流，不触 Agent/工具/redis）。需要工具路径或 vision 的用例自行再 monkeypatch。"""
    from internal.core.language_model.language_model_manager import LanguageModelManager

    fake = _FakeChatModel()
    monkeypatch.setattr(LanguageModelManager, "instantiate", lambda self, provider, model, **kw: fake)
    monkeypatch.setattr(LanguageModelManager, "get_default", lambda self: fake)
    monkeypatch.setattr(LanguageModelManager, "supports_vision", lambda self, p, m: False)
    monkeypatch.setattr(LanguageModelManager, "supports_tool_call", lambda self, p, m: False)
    return fake


@pytest.fixture
def no_after_round_dispatch(monkeypatch):
    """把对话收尾任务 after_round_task.delay 置 no-op（不真正异步派发；用例需要时显式直调 after_round）。"""
    from internal.task import conversation_task

    monkeypatch.setattr(conversation_task.after_round_task, "delay", lambda *a, **k: None)
    yield


@pytest.fixture
def kb_collection(monkeypatch):
    """给知识库用一个独立的临时 Qdrant collection（测试维度 8），用完即删，避免污染真实 ai_dataset。"""
    import uuid

    name = f"ai_dataset_test_{uuid.uuid4().hex[:8]}"
    monkeypatch.setenv("QDRANT_DATASET_COLLECTION", name)
    yield name
    try:
        from internal.core.vector_store.qdrant_vector_store import get_qdrant_client
        client = get_qdrant_client()
        if client.collection_exists(name):
            client.delete_collection(name)
    except Exception:
        pass
