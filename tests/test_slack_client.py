"""tests/test_slack_client.py — slack_project.slack.client の単体テスト"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from slack_project.slack.client import SlackClient


class TestSlackClientDryRun:
    def test_post_message_dry_run(self, capsys):
        client = SlackClient(token="xoxp-test", dry_run=True)
        result = client.post_message(channel="C123", text="hello")
        assert result == {"ok": True, "dry_run": True}
        out = capsys.readouterr().out
        assert "[dry-run] POST chat.postMessage" in out

    def test_api_call_dry_run_json(self, capsys):
        client = SlackClient(token="xoxp-test", dry_run=True)
        result = client.api_call("slackLists.items.list", json={"list_id": "L1"})
        assert result == {"ok": True, "dry_run": True}
        out = capsys.readouterr().out
        assert "[dry-run] POST slackLists.items.list" in out

    def test_api_call_dry_run_params(self, capsys):
        client = SlackClient(token="xoxp-test", dry_run=True)
        result = client.api_call("conversations.history", params={"channel": "C123"})
        assert result == {"ok": True, "dry_run": True}
        out = capsys.readouterr().out
        assert "[dry-run] GET conversations.history" in out

    def test_conversations_history_dry_run(self, capsys):
        client = SlackClient(token="xoxp-test", dry_run=True)
        result = client.conversations_history(channel="C123")
        assert result["ok"] is True

    def test_update_canvas_dry_run(self, capsys):
        client = SlackClient(token="xoxp-test", dry_run=True)
        result = client.update_canvas(channel_id="C123", canvas_id="F456", markdown="# test")
        assert result["ok"] is True

    def test_post_message_with_persona(self, capsys):
        client = SlackClient(token="xoxb-dummy", dry_run=True)
        client.post_message(
            channel="C123",
            text="hello",
            thread_ts="100.000",
            username="TestBot",
            icon_url="https://example.com/i.png",
        )
        out = capsys.readouterr().out
        assert "username" in out and "TestBot" in out
        assert "icon_url" in out


class TestSlackClientApiError:
    def test_conversations_history_api_error_raises(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"ok": False, "error": "invalid_auth"}

        client = SlackClient(token="invalid")
        with patch("requests.get", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="Slack API エラー"):
                client.conversations_history(channel="C123")

    def test_post_message_api_error_raises(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"ok": False, "error": "channel_not_found"}

        client = SlackClient(token="invalid")
        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="Slack API エラー"):
                client.post_message(channel="C_BAD", text="hi")


class TestSlackClientApiCall:
    def test_api_call_with_json_uses_post(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"ok": True, "items": []}

        client = SlackClient(token="xoxp-test")
        with patch("requests.post", return_value=mock_resp) as mock_post:
            client.api_call("slackLists.items.list", json={"list_id": "L1"})
        mock_post.assert_called_once()

    def test_api_call_with_params_uses_get(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"ok": True, "messages": []}

        client = SlackClient(token="xoxp-test")
        with patch("requests.get", return_value=mock_resp) as mock_get:
            client.api_call("conversations.history", params={"channel": "C123"})
        mock_get.assert_called_once()


class TestImport:
    def test_import_from_subpackage(self):
        from slack_project.slack import SlackClient as SC
        assert SC is SlackClient
