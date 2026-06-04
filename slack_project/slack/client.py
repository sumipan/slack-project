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
        canvas_id: str,
        markdown: str,
    ) -> dict[str, Any]:
        """Canvas 全文を markdown で置換する。

        Slack の ``canvases.edit`` API は ``changes`` に 1 件しか受け付けない
        (``no more than 1 items allowed``) ため、フル置換は複数 API call の
        シーケンスで実現する:

        1. ``canvases.sections.lookup`` で既存ヘッダーセクション ID を列挙
        2. 旧セクションを 1 件ずつ ``delete``
        3. ``insert_at_start`` で新 markdown を 1 件で投入

        合計 N+2 リクエスト (N = 旧セクション数 + lookup + insert)。
        Slack のレート制限は ``canvases.edit`` が Tier 3 (おおむね 50/min) なので
        通常の todo Canvas (数十セクション) なら問題ない。
        """
        sections_resp = self._post(
            "canvases.sections.lookup",
            {"canvas_id": canvas_id, "criteria": {"section_types": ["any_header"]}},
        )
        old_section_ids = [s["id"] for s in sections_resp.get("sections", [])]

        # 旧セクションを delete してから新コンテンツを insert する。
        # (順序を逆にすると insert で増えたセクションと既存 ID が混ざりうるので注意)
        for sid in old_section_ids:
            self._post(
                "canvases.edit",
                {
                    "canvas_id": canvas_id,
                    "changes": [{"operation": "delete", "section_id": sid}],
                },
            )

        return self._post(
            "canvases.edit",
            {
                "canvas_id": canvas_id,
                "changes": [
                    {
                        "operation": "insert_at_start",
                        "document_content": {"type": "markdown", "markdown": markdown},
                    }
                ],
            },
        )

    def access_canvas_markdown(self, canvas_id: str) -> str:
        """Canvas の全文 markdown を返す。

        Slack の公開 API には canvas 専用の content-read エンドポイントが無いため、
        canvas を file として `files.info` で参照し、`url_private_download` を
        ダウンロードして本文を取得する。
        Required scope: `files:read`（`canvases:read` だけでは不可）。

        Raises:
            RuntimeError: Slack API エラー、ダウンロード失敗時。
        """
        info = self.api_call("files.info", params={"file": canvas_id})
        file_obj = info.get("file") or {}
        download_url = (
            file_obj.get("url_private_download") or file_obj.get("url_private")
        )
        if not download_url:
            raise RuntimeError(
                f"files.info に url_private_download が含まれていません: canvas_id={canvas_id}"
            )
        resp = requests.get(
            download_url,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.text

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
