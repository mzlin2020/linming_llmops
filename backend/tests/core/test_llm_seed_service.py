"""LlmSeedService.seed_builtin_catalog：幂等灌入 + 不覆盖已存在（真实 DB，本机 SQLite 代跑）。

db_tables 是 session 级、表跨用例存活，故每个用例自行清理灌入的 provider，避免相互污染。
"""
import pytest

_BUILTIN = ["openai", "anthropic", "deepseek", "openai_compatible"]


@pytest.fixture
def seed_service():
    from internal.core.language_model import LanguageModelManager
    from internal.service import LlmSeedService

    return LlmSeedService(LanguageModelManager())


def _cleanup():
    from internal.extension.database_extension import db
    from internal.model import LlmProvider

    with db.auto_commit():
        for name in _BUILTIN:
            row = db.session.query(LlmProvider).filter_by(name=name).first()
            if row:
                db.session.delete(row)  # FK CASCADE 连带删 model


def test_seed_inserts_builtin_catalog(app_context, db_tables, seed_service):
    from internal.extension.database_extension import db
    from internal.model import LlmModel, LlmProvider

    try:
        result = seed_service.seed_builtin_catalog()
        assert result["imported"] >= 4
        assert result["models"] >= 1

        names = {n for (n,) in db.session.query(LlmProvider.name).all()}
        assert set(_BUILTIN) <= names

        # openai 下 gpt-4o-mini 落库且 is_default；密钥不入仓，env 兜底
        openai = db.session.query(LlmProvider).filter_by(name="openai").one()
        assert openai.api_key_cipher == ""
        assert openai.api_key_env == "OPENAI_API_KEY"
        mini = db.session.query(LlmModel).filter_by(
            provider_id=openai.id, model_name="gpt-4o-mini"
        ).one()
        assert mini.is_default is True

        # 聚合网关作为模板预置：默认禁用
        compat = db.session.query(LlmProvider).filter_by(name="openai_compatible").one()
        assert compat.enabled is False

        # 二次运行幂等：全 skip，不重复插入
        result2 = seed_service.seed_builtin_catalog()
        assert result2["imported"] == 0
        assert result2["skipped"] >= 4
        assert db.session.query(LlmProvider).filter_by(name="openai").count() == 1
    finally:
        _cleanup()


def test_seed_skips_existing_provider(app_context, db_tables, seed_service):
    """已存在同名 provider → 跳过，绝不覆盖用户在管理面的改动。"""
    from internal.extension.database_extension import db
    from internal.model import LlmProvider

    with db.auto_commit():
        db.session.add(LlmProvider(
            name="openai", protocol="openai",
            base_url="https://user-edited.example/v1", enabled=True,
        ))

    try:
        result = seed_service.seed_builtin_catalog()
        # openai 被跳过（base_url 仍是用户值，未被内置默认覆盖）
        row = db.session.query(LlmProvider).filter_by(name="openai").one()
        assert row.base_url == "https://user-edited.example/v1"
        assert db.session.query(LlmProvider).filter_by(name="openai").count() == 1
        assert result["skipped"] >= 1
        # 其它内置仍照常灌入
        assert {"anthropic", "deepseek"} <= {
            n for (n,) in db.session.query(LlmProvider.name).all()
        }
    finally:
        _cleanup()
