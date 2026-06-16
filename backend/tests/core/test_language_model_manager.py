"""LanguageModelManager：DB 目录加载 / 凭证解密 / 能力判定 / 算价 / 实例化（真实 DB，本机 SQLite 代跑）。

redis 不可用时版本检查优雅降级（恒 0、加载一次），故本机无 redis 也能跑。
"""
from internal.core.language_model import LanguageModelManager


def test_crypto_roundtrip(monkeypatch):
    monkeypatch.setenv("AI_SECRET_ENCRYPT_KEY", "secret-material")
    from internal.lib import crypto

    cipher = crypto.encrypt("sk-abc123")
    assert cipher and cipher != "sk-abc123"
    assert crypto.decrypt(cipher) == "sk-abc123"
    assert crypto.encrypt("") == "" and crypto.decrypt("") == ""
    assert crypto.decrypt("not-a-valid-token") == ""   # 容错，绝不抛
    assert crypto.mask("sk-abcd1234") == "***1234"


def test_catalog_load_and_capabilities(openai_provider):
    mgr = LanguageModelManager()

    assert any(p.name == "openai" for p in mgr.list_providers())
    me = mgr.get_model_entity("openai", "gpt-4o-mini")
    assert me.model_name == "gpt-4o-mini"
    assert mgr.supports_tool_call("openai", "gpt-4o-mini") is True
    assert mgr.supports_vision("openai", "gpt-4o-mini") is False

    price = mgr.calculate_price("openai", "gpt-4o-mini", 1000, 500)
    assert price["total_price"] == round((1000 * 1.0 + 500 * 2.0) * 0.001, 7)
    assert mgr.calculate_price(None, None, 1, 1)["total_price"] == 0.0


def test_instantiate_returns_chat_model(openai_provider, monkeypatch):
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "openai")
    monkeypatch.setenv("DEFAULT_LLM_MODEL", "gpt-4o-mini")
    mgr = LanguageModelManager()

    chat = mgr.instantiate("openai", "gpt-4o-mini")
    assert chat is not None
    # langchain ChatOpenAI 暴露 model_name；解密后的 key 已注入（构造不触网）。
    assert getattr(chat, "model_name", "") == "gpt-4o-mini"

    # 默认实例化同样可用（get_default 走回落链 → openai/gpt-4o-mini）。
    assert mgr.get_default() is not None


def test_unknown_provider_degrades_to_default(openai_provider, monkeypatch):
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "openai")
    monkeypatch.setenv("DEFAULT_LLM_MODEL", "gpt-4o-mini")
    mgr = LanguageModelManager()

    # 目标 provider 不存在 → 优雅降级到默认 openai/gpt-4o-mini（不抛）。
    chat = mgr.instantiate("ghost-provider", "ghost-model")
    assert getattr(chat, "model_name", "") == "gpt-4o-mini"
