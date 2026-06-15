import os
import time

import pytest


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
