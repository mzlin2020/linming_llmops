"""Phase 3 核心层测试夹具。

通用的假 embedding / Qdrant 守卫（fake_embeddings / qdrant_client_or_skip / kb_collection）已上移到
顶层 tests/conftest.py，供 core 层与 handler 层共享；本文件仅保留 core 专属的 LLM provider 夹具。
"""
import pytest


@pytest.fixture
def openai_provider(app_context, db_tables):
    """播一条启用的 openai/gpt-4o-mini provider+model（含加密 key），用完即删。

    db_tables 是 session 级、表跨用例存活，故必须逐用例清理避免相互污染；
    放进夹具 teardown 比每个用例手写 delete 更稳。
    """
    from internal.extension.database_extension import db
    from internal.lib import crypto
    from internal.model import LlmModel, LlmProvider

    prov = LlmProvider(
        name="openai", protocol="openai",
        api_key_cipher=crypto.encrypt("sk-test"),
        base_url="https://api.example.com/v1", enabled=True,
    )
    db.session.add(prov)
    db.session.flush()
    db.session.add(LlmModel(
        provider_id=prov.id, model_name="gpt-4o-mini", model_type="chat",
        features=["tool_call"],
        pricing={"input": 1.0, "output": 2.0, "unit": "0.001", "currency": "USD"},
        enabled=True,
    ))
    db.session.commit()
    yield prov
    db.session.delete(prov)   # FK ondelete=cascade 连带删 LlmModel
    db.session.commit()
