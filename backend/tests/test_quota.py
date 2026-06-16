"""QuotaService 拍平后的 DB 维度配额：对所有登录用户统一生效（无超管豁免），<=0 表示不限。

纯本机（DB 维度，不依赖 redis）：知识库数上限、单库文档数上限、单文件大小。
redis 维度的限流（命中/灌库冷却/日次数）在 handler 集成测试里用 redis_or_skip 守卫（交 CI）。
"""
import pytest

from internal.exception import ValidateErrorException


def _qs_and_user(app, account_id):
    from app.http.module import injector
    from internal.extension.database_extension import db
    from internal.model import Account
    from internal.service import QuotaService

    return injector.get(QuotaService), db.session.get(Account, account_id)


def test_create_dataset_limit_and_unlimited(app, account, monkeypatch):
    from internal.extension.database_extension import db
    from internal.model import Dataset

    monkeypatch.setitem(app.config, "QUOTA_MAX_DATASETS_PER_USER", 2)
    with app.app_context():
        qs, user = _qs_and_user(app, account)
        qs.check_create_dataset(user)  # 0 个，放行
        with db.auto_commit():
            db.session.add_all([Dataset(user_id=user.id, name="a"), Dataset(user_id=user.id, name="b")])
        # 到上限即拒（无超管豁免：所有登录用户一视同仁）
        with pytest.raises(ValidateErrorException):
            qs.check_create_dataset(user)
        # <=0 = 不限
        monkeypatch.setitem(app.config, "QUOTA_MAX_DATASETS_PER_USER", 0)
        qs.check_create_dataset(user)


def test_max_upload_size_flattened(app, account, monkeypatch):
    with app.app_context():
        qs, user = _qs_and_user(app, account)
        monkeypatch.setitem(app.config, "QUOTA_USER_UPLOAD_MAX_SIZE", 1024)
        assert qs.max_upload_size(user) == 1024
        # <=0 回落到全局 UPLOAD_MAX_SIZE
        monkeypatch.setitem(app.config, "QUOTA_USER_UPLOAD_MAX_SIZE", 0)
        monkeypatch.setitem(app.config, "UPLOAD_MAX_SIZE", 99999)
        assert qs.max_upload_size(user) == 99999


def test_add_documents_doc_count_limit(app, account, monkeypatch):
    from internal.extension.database_extension import db
    from internal.model import Dataset, Document

    # 关掉 redis 维度的灌库预算（cooldown=0 跳过、daily<=0 不限），单测纯 DB 的单库文档数上限
    monkeypatch.setitem(app.config, "QUOTA_MAX_DOCS_PER_DATASET", 1)
    monkeypatch.setitem(app.config, "QUOTA_BUILD_COOLDOWN_SECONDS", 0)
    monkeypatch.setitem(app.config, "QUOTA_BUILD_DAILY_LIMIT", 0)
    with app.app_context():
        qs, user = _qs_and_user(app, account)
        ds = Dataset(user_id=user.id, name="docs-cap")
        with db.auto_commit():
            db.session.add(ds)
        db.session.refresh(ds)
        with db.auto_commit():
            db.session.add(Document(user_id=user.id, dataset_id=ds.id, name="d1", status="waiting"))
        # 已有 1 篇，再加 1 篇 → 2 > 1 → 拒
        with pytest.raises(ValidateErrorException):
            qs.check_add_documents(user, ds.id, 1)
        # <=0 = 不限
        monkeypatch.setitem(app.config, "QUOTA_MAX_DOCS_PER_DATASET", 0)
        qs.check_add_documents(user, ds.id, 5)
