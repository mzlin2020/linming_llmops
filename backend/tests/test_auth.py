"""认证全链路（需 MySQL；本机无 DB 时由 CI 覆盖）。"""
import uuid


def _email() -> str:
    return f"u_{uuid.uuid4().hex[:8]}@test.local"


def _register(client, email=None, password="secret123", name=None):
    return client.post(
        "/api/auth/register",
        json={"email": email or _email(), "password": password, "name": name},
    )


def test_register_success(client, db_tables):
    resp = _register(client)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["access_token"] and data["refresh_token"]
    assert data["account"]["email"] and data["account"]["id"]


def test_register_duplicate(client, db_tables):
    email = _email()
    assert _register(client, email).status_code == 200
    assert _register(client, email).status_code == 422


def test_register_short_password(client, db_tables):
    assert _register(client, password="123").status_code == 422


def test_register_disabled(client, db_tables, app, monkeypatch):
    monkeypatch.setitem(app.config, "ALLOW_REGISTRATION", False)
    assert _register(client).status_code == 403


def test_login_success(client, db_tables):
    email = _email()
    _register(client, email)
    resp = client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["access_token"] and data["refresh_token"]


def test_login_wrong_password(client, db_tables):
    email = _email()
    _register(client, email)
    resp = client.post("/api/auth/login", json={"email": email, "password": "nope"})
    assert resp.status_code == 401


def test_login_unknown_email(client, db_tables):
    resp = client.post("/api/auth/login", json={"email": _email(), "password": "secret123"})
    assert resp.status_code == 401


def test_refresh_success(client, db_tables):
    tokens = _register(client).get_json()["data"]
    resp = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    assert resp.get_json()["data"]["access_token"]


def test_refresh_rejects_access_token(client, db_tables):
    tokens = _register(client).get_json()["data"]
    resp = client.post("/api/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert resp.status_code == 401


def test_me_requires_auth(client, db_tables):
    assert client.get("/api/account/me").status_code == 401


def test_me_invalid_token(client, db_tables):
    resp = client.get("/api/account/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


def test_me_with_token(client, db_tables):
    email = _email()
    tokens = _register(client, email).get_json()["data"]
    resp = client.get("/api/account/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert resp.status_code == 200
    assert resp.get_json()["data"]["email"] == email


def test_me_expired_token(client, db_tables, make_token):
    tokens = _register(client).get_json()["data"]
    headers = {"Authorization": f"Bearer {make_token(tokens['account']['id'], expired=True)}"}
    assert client.get("/api/account/me", headers=headers).status_code == 401
