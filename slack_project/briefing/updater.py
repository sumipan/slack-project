from __future__ import annotations

from pathlib import Path
from typing import Any


def get_briefing_path(project: str) -> Path:
    """projects/<project>/briefing.md のパスを返す。

    project に "projects/" プレフィクスが含まれていても正規化する。
    """
    if project.startswith("projects/"):
        project = project[len("projects/"):]
    return Path("projects") / project / "briefing.md"


def _load_project_config(project: str) -> dict[str, Any]:
    try:
        import yaml
    except ImportError:
        return {}

    config: dict[str, Any] = {}
    for name in ("config.yaml", "config_local.yml", "config.local.yaml"):
        p = Path("projects") / project / name
        if p.exists():
            with open(p, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                config = _deep_merge(config, data)
    return config


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


def _get_canvas_token(config: dict[str, Any]) -> str | None:
    slack = config.get("slack") or {}
    return slack.get("user_token") or slack.get("token")


def _get_canvas_ids(config: dict[str, Any]) -> tuple[str | None, str | None]:
    """Returns (channel_id, canvas_id)."""
    slack = config.get("slack") or {}
    channel_id = slack.get("channel_id") or (config.get("project") or {}).get("slack_channel_id")
    canvas_id = slack.get("canvas_id") or (config.get("project") or {}).get("slack_canvas_id")
    return channel_id, canvas_id


def update_canvas(project: str) -> tuple[bool, str]:
    """briefing.md の内容を Slack Canvas に反映する。

    返り値: (成功フラグ, 出力メッセージ)
    """
    if project.startswith("projects/"):
        project = project[len("projects/"):]

    briefing_path = get_briefing_path(project)
    if not briefing_path.exists():
        return False, f"briefing.md が見つかりません: {briefing_path}"

    config = _load_project_config(project)
    token = _get_canvas_token(config)
    channel_id, canvas_id = _get_canvas_ids(config)

    if not token:
        return False, "Slack トークンが設定されていません"
    if not channel_id or not canvas_id:
        return False, "Slack チャンネル ID または Canvas ID が設定されていません"

    markdown = briefing_path.read_text(encoding="utf-8")

    try:
        import requests

        payload = {
            "channel_id": channel_id,
            "canvas_id": canvas_id,
            "changes": [
                {
                    "operation": "replace",
                    "document_range": {
                        "anchor_block": {"id": "start"},
                        "end_block": {"id": "end"},
                    },
                    "elements": [{"type": "markdown", "text": markdown}],
                }
            ],
        }
        resp = requests.post(
            "https://slack.com/api/canvases.edit",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            return False, f"Slack API エラー: {data.get('error', 'unknown')}"
        return True, f"Canvas を更新しました: {project}"
    except Exception as exc:
        return False, str(exc)
