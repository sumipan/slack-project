import pytest

from slack_project.cli.sync_todo import main


def test_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0


def test_missing_required_arg_exits_two():
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2


def test_not_implemented_returns_one(capsys):
    result = main(["--project", "test"])
    assert result == 1
    captured = capsys.readouterr()
    assert captured.err != ""


def test_fetch_only_flag_is_removed():
    with pytest.raises(SystemExit) as exc_info:
        main(["--project", "test", "--fetch-only"])
    assert exc_info.value.code == 2


def test_check_only_flag_is_removed():
    with pytest.raises(SystemExit) as exc_info:
        main(["--project", "test", "--check-only"])
    assert exc_info.value.code == 2


def test_dry_run_flag_success(tmp_path, monkeypatch, capsys):
    project_root = tmp_path / "projects" / "my-project"
    project_root.mkdir(parents=True)
    (project_root / "todo.md").write_text("## 議事録由来タスク\n- [ ] A\n", encoding="utf-8")
    (project_root / "config.yaml").write_text(
        "slack:\n  user_token: xoxp-test\n  channel_id: C123\n  canvas_id: F456\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = main(["--project", "my-project", "--dry-run"])
    assert result == 0
    captured = capsys.readouterr()
    assert "dry-run" in captured.out


def test_main_returns_int():
    result = main(["--project", "test"])
    assert isinstance(result, int)


def test_canvas_push_success(tmp_path, monkeypatch):
    project_root = tmp_path / "projects" / "my-project"
    project_root.mkdir(parents=True)
    (project_root / "todo.md").write_text("## 議事録由来タスク\n- [ ] A\n", encoding="utf-8")
    (project_root / "config.yaml").write_text(
        "slack:\n  user_token: xoxp-test\n  channel_id: C123\n  canvas_id: F456\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    calls: list[tuple[str, str, str]] = []

    class FakeSlackClient:
        def __init__(self, token: str, *, dry_run: bool = False) -> None:
            self.token = token
            self.dry_run = dry_run

        def update_canvas(self, channel_id: str, canvas_id: str, markdown: str):
            calls.append((channel_id, canvas_id, markdown))
            return {"ok": True}

    monkeypatch.setattr("slack_project.cli.sync_todo.SlackClient", FakeSlackClient)
    result = main(["--project", "my-project"])
    assert result == 0
    assert calls and calls[0][0] == "C123" and calls[0][1] == "F456"
