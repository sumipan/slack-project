from pathlib import Path
from unittest.mock import MagicMock, patch

from slack_project.briefing.updater import get_briefing_path, update_canvas
from slack_project.workspace import ProjectWorkspace


def _ws(tmp_path: Path) -> ProjectWorkspace:
    return ProjectWorkspace(
        projects_root=tmp_path / "projects",
        queue_dir=tmp_path / "jobs",
    )


class TestGetBriefingPath:
    def test_normal(self, tmp_path):
        ws = _ws(tmp_path)
        result = get_briefing_path(ws, "my-project")
        assert result == tmp_path / "projects" / "my-project" / "briefing.md"

    def test_projects_prefix_normalized(self, tmp_path):
        ws = _ws(tmp_path)
        result = get_briefing_path(ws, "projects/my-project")
        assert result == tmp_path / "projects" / "my-project" / "briefing.md"

    def test_returns_path_object(self, tmp_path):
        ws = _ws(tmp_path)
        result = get_briefing_path(ws, "any-project")
        assert isinstance(result, Path)


class TestUpdateCanvas:
    def test_missing_briefing_returns_error(self, tmp_path):
        ws = _ws(tmp_path)
        ok, msg = update_canvas(ws, "nonexistent-project")
        assert ok is False
        assert "briefing.md" in msg

    def test_projects_prefix_normalized(self, tmp_path):
        ws = _ws(tmp_path)
        ok, msg = update_canvas(ws, "projects/nonexistent")
        assert ok is False
        assert "briefing.md" in msg

    def test_canvas_api_called(self, tmp_path):
        ws = _ws(tmp_path)
        proj_dir = ws.projects_root / "my-project"
        proj_dir.mkdir(parents=True)
        (proj_dir / "briefing.md").write_text("# Briefing\nContent here")
        (proj_dir / "config.yaml").write_text(
            "slack:\n  user_token: xoxp-test\n  channel_id: C123\n  canvas_id: F456\n"
        )

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}
        mock_resp.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_resp) as mock_post:
            ok, msg = update_canvas(ws, "my-project")

        assert ok is True
        assert mock_post.called
        call_args = mock_post.call_args
        assert "canvases.edit" in call_args[0][0]
        payload = call_args[1]["json"]
        assert payload["canvas_id"] == "F456"
        assert payload["channel_id"] == "C123"

    def test_missing_token_returns_error(self, tmp_path):
        ws = _ws(tmp_path)
        proj_dir = ws.projects_root / "no-token"
        proj_dir.mkdir(parents=True)
        (proj_dir / "briefing.md").write_text("content")
        (proj_dir / "config.yaml").write_text("slack:\n  channel_id: C123\n  canvas_id: F456\n")

        ok, msg = update_canvas(ws, "no-token")
        assert ok is False
        assert "トークン" in msg

    def test_api_error_returns_failure(self, tmp_path):
        ws = _ws(tmp_path)
        proj_dir = ws.projects_root / "err-proj"
        proj_dir.mkdir(parents=True)
        (proj_dir / "briefing.md").write_text("content")
        (proj_dir / "config.yaml").write_text(
            "slack:\n  user_token: xoxp-test\n  channel_id: C123\n  canvas_id: F456\n"
        )

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": False, "error": "invalid_auth"}
        mock_resp.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_resp):
            ok, msg = update_canvas(ws, "err-proj")

        assert ok is False
        assert "invalid_auth" in msg
