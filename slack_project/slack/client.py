"""slack_project.slack.client — Slack API 薄いラッパー"""
from __future__ import annotations

import json
from typing import Any

try:
    import requests
except ImportError as exc:
    raise ImportError("requests が必要です: pip install requests") from exc

SLACK_API_BASE = "https://slack.com/api"


class SlackClient:
    def __init__(self, token: str, *, dry_run: bool = False) -> None:
        self.token = token
        self.dry_run = dry_run

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.dry_run:
            print(f"[dry-run] POST {method}")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return {"ok": True, "dry_run": True}

        url = f"{SLACK_API_BASE}/{method}"
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API エラー [{method}]: {data.get('error', 'unknown')}")
        return data

    def _get(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.dry_run:
            print(f"[dry-run] GET {method}")
            print(json.dumps(params, ensure_ascii=False, indent=2))
            return {"ok": True, "dry_run": True}

        url = f"{SLACK_API_BASE}/{method}"
        headers = {"Authorization": f"Bearer {self.token}"}
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API エラー [{method}]: {data.get('error', 'unknown')}")
        return data

    def api_call(
        self,
        method: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict[str, Any]:
        if json is not None:
            return self._post(method, json)
        return self._get(method, params or {})

    def post_message(
        self,
        channel: str,
        text: str = "",
        blocks: list[dict] | None = None,
        thread_ts: str | None = None,
        reply_broadcast: bool = False,
        *,
        username: str | None = None,
        icon_url: str | None = None,
        icon_emoji: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"channel": channel, "text": text}
        if blocks:
            payload["blocks"] = blocks
        if thread_ts:
            payload["thread_ts"] = thread_ts
            payload["reply_broadcast"] = reply_broadcast
        if username:
            payload["username"] = username
        if icon_url:
            payload["icon_url"] = icon_url
        if icon_emoji:
            payload["icon_emoji"] = icon_emoji
        return self._post("chat.postMessage", payload)

    def update_canvas(
        self,
        channel_id: str,
        canvas_id: str,
        markdown: str,
    ) -> dict[str, Any]:
        payload = {
            "channel_id": channel_id,
            "canvas_id": canvas_id,
            "changes": [
                {
                    "operation": "replace",
                    "document_range": {"anchor_block": {"id": "start"}, "end_block": {"id": "end"}},
                    "elements": [{"type": "markdown", "text": markdown}],
                }
            ],
        }
        return self._post("canvases.edit", payload)

    def conversations_history(
        self,
        channel: str,
        oldest: str | None = None,
        latest: str | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"channel": channel, "limit": limit}
        if oldest:
            params["oldest"] = oldest
        if latest:
            params["latest"] = latest
        return self._get("conversations.history", params)


__all__ = ["SlackClient"]
