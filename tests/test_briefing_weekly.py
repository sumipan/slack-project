import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from slack_project.briefing.weekly import (
    _calc_period,
    fetch_slack_log,
    post_summary,
    run_auto_update,
)
from slack_project.workspace import ProjectWorkspace

_JST = ZoneInfo("Asia/Tokyo")


def _ws(tmp_path: Path) -> ProjectWorkspace:
    return ProjectWorkspace(
        projects_root=tmp_path / "projects",
        queue_dir=tmp_path / "jobs",
    )


class TestCalcPeriod:
    def test_current_on_wednesday(self):
        wednesday = datetime(2026, 5, 27, 12, 0, 0, tzinfo=_JST)
        with patch("slack_project.briefing.weekly.datetime") as mock_dt:
            mock_dt.now.return_value = wednesday
            mock_dt.strptime = datetime.strptime
            start, end = _calc_period("current", None, None)

        assert start.weekday() == 5
        assert start.hour == 0
        assert end.weekday() == 4
        assert end.hour == 23
        assert end.minute == 59
        assert end.second == 59

    def test_current_on_saturday(self):
        saturday = datetime(2026, 5, 23, 10, 0, 0, tzinfo=_JST)
        with patch("slack_project.briefing.weekly.datetime") as mock_dt:
            mock_dt.now.return_value = saturday
            mock_dt.strptime = datetime.strptime
            start, end = _calc_period("current", None, None)

        assert start.date() == saturday.date()
        assert start.hour == 0
        assert end.weekday() == 4
        assert end.hour == 23

    def test_last_week(self):
        wednesday = datetime(2026, 5, 27, 12, 0, 0, tzinfo=_JST)
        with patch("slack_project.briefing.weekly.datetime") as mock_dt:
            mock_dt.now.return_value = wednesday
            mock_dt.strptime = datetime.strptime
            start, end = _calc_period("last", None, None)

        assert start.weekday() == 5
        assert end.weekday() == 4
        assert (end - start).days == 6

    def test_with_since_until(self):
        start, end = _calc_period("last", "2026-01-01", "2026-01-07")
        assert start.year == 2026
        assert start.month == 1
        assert start.day == 1
        assert start.hour == 0
        assert end.day == 7
        assert end.hour == 23
        assert end.minute == 59
        assert end.second == 59


class TestFetchSlackLog:
    def _make_mock_resp(self, messages, has_more=False, status=200):
        mock = MagicMock()
        mock.status_code = status
        mock.json.return_value = {"ok": True, "messages": messages, "has_more": has_more}
        return mock

    def test_success(self, tmp_path):
        ws = _ws(tmp_path)
        proj_dir = ws.projects_root / "my-project"
        proj_dir.mkdir(parents=True)
        (proj_dir / "config.yaml").write_text(
            "slack:\n  user_token: xoxp-test\n  channel_id: C123\n"
        )

        ts = 1748300000.0
        mock_resp = self._make_mock_resp(
            [{"ts": str(ts), "user": "U001", "text": "hello", "reply_count": 0}]
        )

        with patch("requests.get", return_value=mock_resp):
            ok, msg = fetch_slack_log(ws, "my-project", week="last")

        assert ok is True
        assert "取得件数" in msg
        log_files = list((proj_dir / "assets").glob("*_Slackのログ.md"))
        assert len(log_files) == 1

    def test_http_429_error(self, tmp_path):
        ws = _ws(tmp_path)
        proj_dir = ws.projects_root / "my-project"
        proj_dir.mkdir(parents=True)
        (proj_dir / "config.yaml").write_text(
            "slack:\n  user_token: xoxp-test\n  channel_id: C123\n"
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.json.return_value = {}

        with patch("requests.get", return_value=mock_resp):
            ok, msg = fetch_slack_log(ws, "my-project", week="last")

        assert ok is False
        assert "429" in msg

    def test_missing_project_config(self, tmp_path):
        ws = _ws(tmp_path)
        proj_dir = ws.projects_root / "nonexistent-project"
        proj_dir.mkdir(parents=True)

        ok, msg = fetch_slack_log(ws, "nonexistent-project", week="last")
        assert ok is False

    def test_missing_token(self, tmp_path):
        ws = _ws(tmp_path)
        proj_dir = ws.projects_root / "no-token"
        proj_dir.mkdir(parents=True)
        (proj_dir / "config.yaml").write_text("slack:\n  channel_id: C123\n")

        ok, msg = fetch_slack_log(ws, "no-token")
        assert ok is False
        assert "トークン" in msg


class TestPostSummary:
    def test_dry_run(self, tmp_path):
        ws = _ws(tmp_path)
        summary = tmp_path / "summary.md"
        summary.write_text("# Weekly Summary")

        ok, msg = post_summary(ws, "my-project", summary, dry_run=True)
        assert ok is True
        assert "dry-run" in msg

    def test_success(self, tmp_path):
        ws = _ws(tmp_path)
        proj_dir = ws.projects_root / "my-project"
        proj_dir.mkdir(parents=True)
        (proj_dir / "config.yaml").write_text(
            "slack:\n  user_token: xoxp-test\n  channel_id: C123\n"
        )
        summary = tmp_path / "summary.md"
        summary.write_text("# Weekly Summary")

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}
        mock_resp.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_resp):
            ok, msg = post_summary(ws, "my-project", summary)

        assert ok is True

    def test_missing_summary_file(self, tmp_path):
        ws = _ws(tmp_path)
        ok, msg = post_summary(ws, "my-project", tmp_path / "nonexistent.md")
        assert ok is False
        assert "見つかりません" in msg


class TestRunAutoUpdate:
    def test_dry_run_no_projects(self, tmp_path):
        ws = _ws(tmp_path)
        ws.projects_root.mkdir(parents=True)
        ok, msg = run_auto_update(ws, dry_run=True)
        assert ok is True
        assert "見つかりません" in msg

    def test_dry_run_with_projects(self, tmp_path):
        ws = _ws(tmp_path)
        proj_dir = ws.projects_root / "proj-a"
        proj_dir.mkdir(parents=True)
        (proj_dir / "config.yaml").write_text(
            "slack:\n  channel_id: C123\nweekly_summary:\n  enabled: true\n"
        )
        (proj_dir / "config_local.yml").write_text("slack:\n  user_token: xoxp-test\n")

        ok, msg = run_auto_update(ws, dry_run=True)
        assert ok is True
        assert "proj-a" in msg
        assert "dry-run" in msg


class TestFetchSlackLogJsonl:
    PARENT_A = "1748300000.000100"
    PARENT_B = "1748300600.000200"
    REPLY = "1748300300.000300"

    def _setup(self, tmp_path):
        ws = _ws(tmp_path)
        proj_dir = ws.projects_root / "my-project"
        proj_dir.mkdir(parents=True)
        (proj_dir / "config.yaml").write_text(
            "slack:\n  user_token: xoxp-test\n  channel_id: C123\n"
        )
        return ws, proj_dir

    def _fake_get(self, url, params=None, headers=None, timeout=None):
        resp = MagicMock()
        resp.status_code = 200
        if url.endswith("conversations.history"):
            messages = [
                {"ts": self.PARENT_B, "bot_id": "B002", "text": "second"},
                {
                    "ts": self.PARENT_A,
                    "user": "U001",
                    "text": "first",
                    "reply_count": 1,
                    "thread_ts": self.PARENT_A,
                },
            ]
        else:
            messages = [
                {"ts": self.PARENT_A, "user": "U001", "text": "first"},
                {
                    "ts": self.REPLY,
                    "user": "U003",
                    "text": "reply",
                    "thread_ts": self.PARENT_A,
                },
            ]
        resp.json.return_value = {"ok": True, "messages": messages, "has_more": False}
        return resp

    def _run(self, ws, **kwargs):
        with patch("requests.get", side_effect=self._fake_get), patch(
            "slack_project.briefing.weekly.time.sleep"
        ):
            return fetch_slack_log(
                ws, "my-project", since="2025-05-26", until="2025-05-28", **kwargs
            )

    def _jsonl_path(self, d: Path) -> Path:
        date = datetime.fromtimestamp(float(self.PARENT_A), tz=_JST).strftime("%Y-%m-%d")
        return d / f"{date}.jsonl"

    def test_writes_records(self, tmp_path):
        ws, _ = self._setup(tmp_path)
        d = tmp_path / "jsonl"
        ok, _ = self._run(ws, jsonl_dir=d)
        assert ok is True

        path = self._jsonl_path(d)
        records = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines()]
        assert len(records) == 3
        for rec in records:
            assert set(rec) == {"id", "ts", "author", "text", "thread_ts", "raw"}
            assert rec["id"] == rec["ts"]
        by_id = {r["id"]: r for r in records}
        assert by_id[self.REPLY]["thread_ts"] == self.PARENT_A
        assert by_id[self.REPLY]["author"] == "U003"
        assert by_id[self.PARENT_A]["thread_ts"] is None
        assert by_id[self.PARENT_B]["author"] == "B002"
        assert by_id[self.PARENT_B]["raw"]["text"] == "second"

    def test_idempotent(self, tmp_path):
        ws, _ = self._setup(tmp_path)
        d = tmp_path / "jsonl"
        self._run(ws, jsonl_dir=d)
        self._run(ws, jsonl_dir=d)
        lines = self._jsonl_path(d).read_text(encoding="utf-8").splitlines()
        assert len(lines) == 3
        assert len({json.loads(ln)["id"] for ln in lines}) == 3

    def test_no_jsonl_by_default(self, tmp_path):
        ws, proj_dir = self._setup(tmp_path)
        ok_default, msg_default = self._run(ws)
        md_default = next((proj_dir / "assets").glob("*.md")).read_text(encoding="utf-8")
        assert not list(tmp_path.rglob("*.jsonl"))

        d = tmp_path / "jsonl"
        ok_jsonl, msg_jsonl = self._run(ws, jsonl_dir=d)
        md_jsonl = next((proj_dir / "assets").glob("*.md")).read_text(encoding="utf-8")

        assert ok_default is True and ok_jsonl is True
        assert msg_default == msg_jsonl
        assert md_default == md_jsonl
        assert [p.parent for p in tmp_path.rglob("*.jsonl")] == [d]
