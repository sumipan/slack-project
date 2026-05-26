"""tests/test_slack_fetch.py — slack_project.slack.fetch の単体テスト"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from slack_project.slack.fetch import fetch_weekly_logs, get_week_ranges
from slack_project.slack.client import SlackClient

TZ = ZoneInfo("Asia/Tokyo")


def dt(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=TZ)


class TestGetWeekRanges:
    def test_same_week(self):
        """受け入れ条件1: 同一週内の範囲 → 1週のみ"""
        result = get_week_ranges(dt(2026, 4, 29), dt(2026, 5, 1))
        assert len(result) == 1
        sat, fri = result[0]
        assert sat.date() == datetime(2026, 4, 25).date()
        assert fri.date() == datetime(2026, 5, 1).date()
        assert fri.hour == 23 and fri.minute == 59 and fri.second == 59

    def test_multiple_weeks(self):
        result = get_week_ranges(dt(2026, 4, 20), dt(2026, 5, 2))
        assert len(result) == 3
        assert result[0][0].date() == datetime(2026, 4, 18).date()
        assert result[2][0].date() == datetime(2026, 5, 2).date()

    def test_same_day(self):
        result = get_week_ranges(dt(2026, 5, 2), dt(2026, 5, 2))
        assert len(result) == 1

    def test_from_after_to(self):
        """受け入れ条件6: from_date > to_date → 空リスト"""
        result = get_week_ranges(dt(2026, 5, 2), dt(2026, 4, 30))
        assert result == []

    def test_saturday_boundary(self):
        result = get_week_ranges(dt(2026, 4, 25), dt(2026, 4, 25))
        sat, fri = result[0]
        assert sat.hour == 0 and sat.minute == 0 and sat.second == 0
        assert fri.hour == 23 and fri.minute == 59 and fri.second == 59


class TestFetchWeeklyLogs:
    def _make_client(self, messages=None):
        client = MagicMock(spec=SlackClient)
        resp = {
            "ok": True,
            "messages": messages or [],
            "has_more": False,
            "response_metadata": {"next_cursor": ""},
        }
        client.conversations_history.return_value = resp
        return client

    def test_skip_existing_file(self, tmp_path: Path):
        """既存ファイルをスキップ → skip カウントが増える"""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "20260425_20260501_Slackのログ.md").write_text("dummy")

        client = self._make_client()
        result = fetch_weekly_logs(client, "C123", dt(2026, 4, 25), dt(2026, 5, 1), output_dir)
        assert result["skip"] == 1
        assert result["ok"] == 0
        assert result["fail"] == 0
        client.conversations_history.assert_not_called()

    def test_creates_output_dir(self, tmp_path: Path):
        """存在しない output_dir を渡した場合にディレクトリが自動作成される"""
        output_dir = tmp_path / "new_dir"
        assert not output_dir.exists()

        client = self._make_client()
        fetch_weekly_logs(client, "C123", dt(2026, 4, 25), dt(2026, 5, 1), output_dir)
        assert output_dir.exists()

    def test_fetch_writes_file(self, tmp_path: Path):
        """ファイルが存在しない場合に API 呼び出しでファイルを作成する"""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        msg = {"ts": "1745000000.000000", "user": "U1", "text": "こんにちは"}
        client = self._make_client(messages=[msg])
        result = fetch_weekly_logs(client, "C123", dt(2026, 4, 25), dt(2026, 5, 1), output_dir)
        assert result["ok"] == 1
        assert result["fail"] == 0
        files = list(output_dir.glob("*.md"))
        assert len(files) == 1

    def test_api_failure_counts_fail(self, tmp_path: Path):
        """API 呼び出し失敗時に fail カウントが増える"""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        client = MagicMock(spec=SlackClient)
        client.conversations_history.side_effect = RuntimeError("Slack API エラー")
        result = fetch_weekly_logs(client, "C123", dt(2026, 4, 25), dt(2026, 5, 1), output_dir)
        assert result["fail"] == 1
        assert result["ok"] == 0

    def test_safe_ratelimit(self, tmp_path: Path):
        """safe_ratelimit=True 時は sleep が挿入される"""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        client = self._make_client()
        with patch("slack_project.slack.fetch.time.sleep") as mock_sleep:
            fetch_weekly_logs(
                client, "C123",
                dt(2026, 4, 20), dt(2026, 5, 2),
                output_dir,
                safe_ratelimit=True,
            )
        assert mock_sleep.called


class TestImport:
    def test_import_from_module(self):
        from slack_project.slack.fetch import fetch_weekly_logs, get_week_ranges
        assert callable(fetch_weekly_logs)
        assert callable(get_week_ranges)

    def test_import_from_package(self):
        from slack_project.slack import fetch_weekly_logs, get_week_ranges
        assert callable(fetch_weekly_logs)
        assert callable(get_week_ranges)
