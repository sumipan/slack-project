"""Migration CLI round-trip tests."""
from pathlib import Path

import pytest

from slack_project.cli.migrate_canvas_keys import migrate_projects


def _write_config(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestMigrateProjects:
    def test_renames_canvas_id_to_briefing_canvas_id(self, tmp_path):
        cfg = tmp_path / "proj" / "config.yaml"
        _write_config(cfg, "slack:\n  user_token: xoxp-test\n  canvas_id: F123\n")

        migrate_projects(tmp_path, dry_run=False)

        content = cfg.read_text(encoding="utf-8")
        assert "briefing_canvas_id: F123" in content
        assert "  canvas_id:" not in content

    def test_dry_run_does_not_modify_file(self, tmp_path):
        cfg = tmp_path / "proj" / "config.yaml"
        original = "slack:\n  user_token: xoxp-test\n  canvas_id: F123\n"
        _write_config(cfg, original)

        migrate_projects(tmp_path, dry_run=True)

        assert cfg.read_text(encoding="utf-8") == original

    def test_dry_run_returns_diff(self, tmp_path, capsys):
        cfg = tmp_path / "proj" / "config.yaml"
        _write_config(cfg, "slack:\n  canvas_id: F123\n")

        migrate_projects(tmp_path, dry_run=True)

        captured = capsys.readouterr()
        assert "briefing_canvas_id" in captured.out

    def test_skips_file_already_having_briefing_canvas_id(self, tmp_path, capsys):
        cfg = tmp_path / "proj" / "config.yaml"
        content = "slack:\n  briefing_canvas_id: F_NEW\n  canvas_id: F_OLD\n"
        _write_config(cfg, content)

        migrate_projects(tmp_path, dry_run=False)

        assert cfg.read_text(encoding="utf-8") == content
        captured = capsys.readouterr()
        assert "スキップ" in captured.out or "skip" in captured.out.lower()

    def test_preserves_comments(self, tmp_path):
        cfg = tmp_path / "proj" / "config.yaml"
        _write_config(
            cfg,
            "slack:\n  user_token: xoxp-test  # Slack ユーザートークン\n  canvas_id: F123  # ブリーフィング用\n",
        )

        migrate_projects(tmp_path, dry_run=False)

        content = cfg.read_text(encoding="utf-8")
        assert "briefing_canvas_id: F123" in content
        assert "#" in content

    def test_handles_config_local_yml(self, tmp_path):
        cfg = tmp_path / "proj" / "config_local.yml"
        _write_config(cfg, "slack:\n  canvas_id: F_LOCAL\n")

        migrate_projects(tmp_path, dry_run=False)

        content = cfg.read_text(encoding="utf-8")
        assert "briefing_canvas_id: F_LOCAL" in content

    def test_handles_config_local_yaml(self, tmp_path):
        cfg = tmp_path / "proj" / "config.local.yaml"
        _write_config(cfg, "slack:\n  canvas_id: F_LOCAL2\n")

        migrate_projects(tmp_path, dry_run=False)

        content = cfg.read_text(encoding="utf-8")
        assert "briefing_canvas_id: F_LOCAL2" in content

    def test_no_canvas_id_file_unchanged(self, tmp_path):
        cfg = tmp_path / "proj" / "config.yaml"
        original = "slack:\n  user_token: xoxp-test\n  channel_id: C123\n"
        _write_config(cfg, original)

        migrate_projects(tmp_path, dry_run=False)

        assert cfg.read_text(encoding="utf-8") == original

    def test_renames_project_slack_canvas_id(self, tmp_path):
        cfg = tmp_path / "proj" / "config.yaml"
        _write_config(
            cfg,
            "project:\n  slack_canvas_id: F_PROJ\nslack:\n  user_token: xoxp-test\n",
        )

        migrate_projects(tmp_path, dry_run=False)

        content = cfg.read_text(encoding="utf-8")
        assert "slack_briefing_canvas_id: F_PROJ" in content
        assert "slack_canvas_id:" not in content

    def test_multiple_projects(self, tmp_path):
        for name in ("proj-a", "proj-b"):
            _write_config(
                tmp_path / name / "config.yaml",
                f"slack:\n  canvas_id: F_{name}\n",
            )

        migrate_projects(tmp_path, dry_run=False)

        for name in ("proj-a", "proj-b"):
            content = (tmp_path / name / "config.yaml").read_text(encoding="utf-8")
            assert f"briefing_canvas_id: F_{name}" in content


class TestMigrateProjectsCLI:
    def test_cli_dry_run(self, tmp_path):
        cfg = tmp_path / "proj" / "config.yaml"
        _write_config(cfg, "slack:\n  canvas_id: F123\n")

        from slack_project.cli.migrate_canvas_keys import main

        result = main(["--projects-dir", str(tmp_path), "--dry-run"])
        assert result == 0
        assert cfg.read_text(encoding="utf-8") == "slack:\n  canvas_id: F123\n"

    def test_cli_apply(self, tmp_path):
        cfg = tmp_path / "proj" / "config.yaml"
        _write_config(cfg, "slack:\n  canvas_id: F123\n")

        from slack_project.cli.migrate_canvas_keys import main

        result = main(["--projects-dir", str(tmp_path)])
        assert result == 0
        assert "briefing_canvas_id: F123" in cfg.read_text(encoding="utf-8")

    def test_cli_missing_dir_returns_error(self):
        from slack_project.cli.migrate_canvas_keys import main

        result = main(["--projects-dir", "/nonexistent/path/xyz"])
        assert result == 1
