"""默认 provider/model 解析：配置 dict → env → 内置默认（OpenAI 兼容，无任何厂商专有硬编码）。"""
from internal.core.language_model.defaults import resolve_default_provider_model


def test_resolve_from_cfg():
    assert resolve_default_provider_model({"provider": "x", "model": "y"}) == ("x", "y")


def test_resolve_from_env(monkeypatch):
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "p")
    monkeypatch.setenv("DEFAULT_LLM_MODEL", "m")
    assert resolve_default_provider_model() == ("p", "m")


def test_resolve_fallback_is_openai(monkeypatch):
    monkeypatch.delenv("DEFAULT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("DEFAULT_LLM_MODEL", raising=False)
    # 关键回归：内置默认必须是厂商中立的 OpenAI 兼容值，不得回退到任何厂商专有默认。
    assert resolve_default_provider_model() == ("openai", "gpt-4o-mini")


def test_cfg_overrides_env(monkeypatch):
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "p")
    monkeypatch.setenv("DEFAULT_LLM_MODEL", "m")
    assert resolve_default_provider_model({"provider": "cfgp"}) == ("cfgp", "m")
