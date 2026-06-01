from __future__ import annotations

from pathlib import Path
from typing import Any

from slack_project.config_loader import load_project_config
from slack_project.workspace import ProjectWorkspace, normalize_project_name


def get_briefing_path(workspace: ProjectWorkspace, project: str) -> Path:
    return workspace.briefing_path(project)


def _get_canvas_token(config: dict[str, Any]) -> str | None:
    slack = config.get("slack") or {}
    return slack.get("user_token") or slack.get("token")


def _get_canvas_ids(config: dict[str, Any]) -> tuple[str | None, str | None]:
    slack = config.get("slack") or {}
    channel_id = slack.get("channel_id") or (config.get("project") or {}).get("slack_channel_id")
    canvas_id = slack.get("canvas_id") or (config.get("project") or {}).get("slack_canvas_id")
    return channel_id, canvas_id


def update_canvas(workspace: ProjectWorkspace, project: str) -> tuple[bool, str]:
    project_name = normalize_project_name(project)
    briefing_path = workspace.briefing_path(project_name)
    if not briefing_path.exists():
        return False, f"briefing.md が見つかりません: {briefing_path}"

    config = load_project_config(workspace.project_dir(project_name))
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
            json=payload,  # type: ignore[arg-type]
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            return False, f"Slack API エラー: {data.get('error', 'unknown')}"
        return True, f"Canvas を更新しました: {project_name}"
    except Exception as exc:
        return False, str(exc)
