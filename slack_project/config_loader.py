from __future__ import annotations

from pathlib import Path
from typing import Any


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if value is None:
            continue
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_project_config(project_root: Path) -> dict[str, Any]:
    """project_root 配下の config YAML をマージ読み込みする。"""
    try:
        import yaml
    except ImportError:
        return {}

    config: dict[str, Any] = {}
    for name in ("config.yaml", "config_local.yml", "config.local.yaml"):
        p = project_root / name
        if p.exists():
            with open(p, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                config = _deep_merge(config, data)
    return config


def get_slack_token(config: dict[str, Any]) -> str | None:
    """config から Slack トークンを取得する。"""
    slack = config.get("slack") or {}
    return slack.get("user_token") or slack.get("token") or config.get("slack_token")
