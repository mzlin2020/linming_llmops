"""模型目录 YAML 种子加载器（纯解析，不碰 DB）。

遍历 <providers_dir>/<name>/provider.yaml + 同目录其余 *.yaml（每个一张模型卡），解析为结构化 dict。
单个文件坏了只跳过不抛，保证开机种子不因一份坏 YAML 崩。
字段对齐 ai_llm_provider / ai_llm_model 列：base_url 是静态默认值，密钥不入仓（只声明 api_key_env，
运行期凭证读取回落环境变量）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

_PROVIDERS_DIR = Path(__file__).parent / "providers"


def _load_yaml(path: Path) -> dict:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_seed_providers(
    providers_dir: Optional[Union[str, Path]] = None,
) -> list[dict[str, Any]]:
    """返回 [{provider 字段..., "models": [模型卡字段...]}]，顺序按目录名排序。"""
    base = Path(providers_dir) if providers_dir else _PROVIDERS_DIR
    out: list[dict[str, Any]] = []
    if not base.is_dir():
        return out

    for sub in sorted(base.iterdir()):
        if not sub.is_dir() or sub.name.startswith(("_", ".")):
            continue
        provider_file = sub / "provider.yaml"
        if not provider_file.exists():
            continue
        try:
            pdata = _load_yaml(provider_file)
        except Exception:  # noqa: BLE001 — 坏 YAML 跳过该 provider，不连累其它
            continue

        provider: dict[str, Any] = {
            "name": pdata.get("name") or sub.name,
            "label": pdata.get("label") or {},
            "description": pdata.get("description") or {},
            "icon": pdata.get("icon") or "",
            "background": pdata.get("background") or "",
            "supported_model_types": pdata.get("supported_model_types") or ["chat"],
            "protocol": pdata.get("protocol") or "openai",
            "multi_channel": bool(pdata.get("multi_channel", False)),
            "base_url": pdata.get("base_url") or "",
            "api_key_env": pdata.get("api_key_env") or "",
            "enabled": bool(pdata.get("enabled", True)),
            "sort": int(pdata.get("sort") or 0),
            "models": [],
        }

        models: list[dict[str, Any]] = []
        for yml in sorted(sub.glob("*.yaml")):
            if yml.name == "provider.yaml":
                continue
            try:
                md = _load_yaml(yml)
            except Exception:  # noqa: BLE001 — 坏模型卡跳过，不连累其它
                continue
            if not md.get("model_name"):
                continue
            models.append({
                "model_name": md["model_name"],
                "label": md.get("label") or {},
                "model_type": md.get("model_type") or "chat",
                "features": md.get("features") or [],
                "context_window": int(md.get("context_window") or 4096),
                "max_output_tokens": md.get("max_output_tokens"),
                "parameter_rules": md.get("parameter_rules") or [],
                "pricing": md.get("pricing"),
                "deprecated": bool(md.get("deprecated", False)),
                "admin_only": bool(md.get("admin_only", False)),
                "is_default": bool(md.get("is_default", False)),
                "enabled": bool(md.get("enabled", True)),
                "sort": int(md.get("sort") or 0),
            })
        provider["models"] = models
        out.append(provider)
    return out
