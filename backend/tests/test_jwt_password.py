"""纯单元测试（无 DB）：密码哈希 + JWT 签发/解析。"""
from types import SimpleNamespace

import pytest

from internal.exception import UnauthorizedException
from internal.service import JwtService
from pkg.password import hash_password, verify_password


def test_password_hash_roundtrip():
    h = hash_password("secret123")
    assert h and h != "secret123"
    assert verify_password("secret123", h)
    assert not verify_password("wrong", h)
    assert not verify_password("secret123", "")


def test_jwt_access_roundtrip(app_context):
    svc = JwtService()
    acc = SimpleNamespace(id=42, email="a@test.local")
    token = svc.generate_access_token(acc)
    payload = svc.parse_token(token, expected_type="access")
    assert payload["sub"] == "42"
    assert payload["type"] == "access"
    assert payload["email"] == "a@test.local"


def test_jwt_refresh_roundtrip(app_context):
    svc = JwtService()
    acc = SimpleNamespace(id=7, email="b@test.local")
    token = svc.generate_refresh_token(acc)
    payload = svc.parse_token(token, expected_type="refresh")
    assert payload["type"] == "refresh"


def test_jwt_type_mismatch(app_context):
    svc = JwtService()
    acc = SimpleNamespace(id=1, email="c@test.local")
    access = svc.generate_access_token(acc)
    with pytest.raises(UnauthorizedException):
        svc.parse_token(access, expected_type="refresh")


def test_jwt_expired(app_context, make_token):
    svc = JwtService()
    with pytest.raises(UnauthorizedException):
        svc.parse_token(make_token(1, expired=True))


def test_jwt_invalid(app_context):
    svc = JwtService()
    with pytest.raises(UnauthorizedException):
        svc.parse_token("not-a-jwt")
