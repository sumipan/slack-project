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
        result = client.update_canvas(canvas_id="F456", markdown="# test")
        assert result["ok"] is True

    def test_update_canvas_uses_lookup_and_insert_at_start_plus_delete(self):
        """real path: canvases.sections.lookup → canvases.edit with insert_at_start + delete per old section"""
        client = SlackClient(token="xoxp-test")
        with patch.object(client, "_post") as mock_post:
            # 1st call: sections.lookup returns 2 old sections
            # 2nd call: canvases.edit returns ok
            mock_post.side_effect = [
                {"ok": True, "sections": [{"id": "sec1"}, {"id": "sec2"}]},
                {"ok": True},
            ]
            result = client.update_canvas(canvas_id="F456", markdown="## new")
            assert result == {"ok": True}
            assert mock_post.call_count == 2
            # First call: lookup
            first_args = mock_post.call_args_list[0][0]
            assert first_args[0] == "canvases.sections.lookup"
            assert first_args[1]["criteria"]["section_types"] == ["any_header"]
            # Second call: edit with batched changes
            second_args = mock_post.call_args_list[1][0]
            assert second_args[0] == "canvases.edit"
            changes = second_args[1]["changes"]
            assert changes[0]["operation"] == "insert_at_start"
            assert changes[0]["document_content"] == {"type": "markdown", "markdown": "## new"}
            assert {c["operation"] for c in changes[1:]} == {"delete"}
            assert [c["section_id"] for c in changes[1:]] == ["sec1", "sec2"]

    def test_update_canvas_empty_lookup_still_inserts(self):
        """If the canvas has no existing header sections, only insert_at_start is emitted."""
        client = SlackClient(token="xoxp-test")
        with patch.object(client, "_post") as mock_post:
            mock_post.side_effect = [{"ok": True, "sections": []}, {"ok": True}]
            client.update_canvas(canvas_id="F456", markdown="## fresh")
            changes = mock_post.call_args_list[1][0][1]["changes"]
            assert len(changes) == 1
            assert changes[0]["operation"] == "insert_at_start"

    def test_access_canvas_markdown_returns_downloaded_text(self):
        """access_canvas_markdown → files.info → GET url_private_download with auth header"""
        client = SlackClient(token="xoxp-test")
        files_info = {"ok": True, "file": {"url_private_download": "https://files.slack.com/x"}}
        download_resp = MagicMock()
        download_resp.text = "## canvas content"
        download_resp.raise_for_status.return_value = None
        with patch.object(client, "api_call", return_value=files_info) as mock_api, \
             patch("slack_project.slack.client.requests.get", return_value=download_resp) as mock_get:
            text = client.access_canvas_markdown("F0CANVAS")
        assert text == "## canvas content"
        mock_api.assert_called_once_with("files.info", params={"file": "F0CANVAS"})
        args, kwargs = mock_get.call_args
        assert args[0] == "https://files.slack.com/x"
        assert kwargs["headers"] == {"Authorization": "Bearer xoxp-test"}

    def test_access_canvas_markdown_falls_back_to_url_private(self):
        client = SlackClient(token="xoxp-test")
        files_info = {"ok": True, "file": {"url_private": "https://files.slack.com/y"}}
        download_resp = MagicMock()
        download_resp.text = "## body"
        download_resp.raise_for_status.return_value = None
        with patch.object(client, "api_call", return_value=files_info), \
             patch("slack_project.slack.client.requests.get", return_value=download_resp) as mock_get:
            client.access_canvas_markdown("F0CANVAS")
        assert mock_get.call_args[0][0] == "https://files.slack.com/y"

    def test_access_canvas_markdown_raises_when_no_url(self):
        client = SlackClient(token="xoxp-test")
        with patch.object(client, "api_call", return_value={"ok": True, "file": {}}):
            with pytest.raises(RuntimeError, match="url_private_download"):
                client.access_canvas_markdown("F0CANVAS")

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
