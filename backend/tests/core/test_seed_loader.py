"""seed_loader：YAML 内置目录解析（纯函数，不碰 DB / app）。"""
from pathlib import Path

from internal.core.language_model.seed_loader import load_seed_providers


def test_loads_bundled_builtin_providers():
    """自带的 4 个内置 provider 都能解析，字段映射对齐 DB 列。"""
    providers = {p["name"]: p for p in load_seed_providers()}
    assert {"openai", "anthropic", "deepseek", "openai_compatible"} <= set(providers)

    openai = providers["openai"]
    assert openai["protocol"] == "openai"
    assert openai["base_url"] == "https://api.openai.com/v1"
    assert openai["api_key_env"] == "OPENAI_API_KEY"
    assert openai["enabled"] is True
    names = {m["model_name"] for m in openai["models"]}
    assert {"gpt-4o", "gpt-4o-mini"} <= names
    mini = next(m for m in openai["models"] if m["model_name"] == "gpt-4o-mini")
    assert mini["is_default"] is True
    assert "tool_call" in mini["features"]

    # anthropic 走原生协议；聚合网关默认 disabled（作为模板预置）
    assert providers["anthropic"]["protocol"] == "anthropic"
    assert providers["openai_compatible"]["enabled"] is False


def test_skips_broken_and_modelless_yaml(tmp_path: Path):
    """坏 provider.yaml / 坏模型卡 / 缺 model_name 都跳过，不连累其它。"""
    good = tmp_path / "good"
    good.mkdir()
    (good / "provider.yaml").write_text(
        "name: good\nprotocol: openai\nbase_url: https://x/v1\n", encoding="utf-8"
    )
    (good / "m1.yaml").write_text("model_name: m1\nmodel_type: chat\n", encoding="utf-8")
    (good / "m_bad.yaml").write_text("model_name: 'unterminated\n", encoding="utf-8")  # 坏 YAML
    (good / "m_nomodel.yaml").write_text("label: {zh_Hans: x}\n", encoding="utf-8")  # 缺 model_name

    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "provider.yaml").write_text("name: 'unterminated\n", encoding="utf-8")  # 坏 YAML

    (tmp_path / "no_provider_yaml").mkdir()  # 无 provider.yaml → 跳过

    providers = {p["name"]: p for p in load_seed_providers(tmp_path)}
    assert set(providers) == {"good"}
    assert {m["model_name"] for m in providers["good"]["models"]} == {"m1"}


def test_missing_dir_returns_empty(tmp_path: Path):
    assert load_seed_providers(tmp_path / "nope") == []
