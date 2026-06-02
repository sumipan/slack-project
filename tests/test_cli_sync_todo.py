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


def _setup_project(tmp_path, todo_text: str) -> None:
    project_root = tmp_path / "projects" / "my-project"
    project_root.mkdir(parents=True)
    (project_root / "todo.md").write_text(todo_text, encoding="utf-8")
    (project_root / "config.yaml").write_text(
        "slack:\n  user_token: xoxp-test\n  channel_id: C123\n  canvas_id: F456\n",
        encoding="utf-8",
    )


def _run_canvas_push(tmp_path, monkeypatch, *, dry_run: bool = False) -> list[tuple[str, str]]:
    monkeypatch.chdir(tmp_path)
    calls: list[tuple[str, str]] = []

    class FakeSlackClient:
        def __init__(self, token: str, *, dry_run: bool = False) -> None:
            self.token = token
            self.dry_run = dry_run

        def update_canvas(self, canvas_id: str, markdown: str):
            calls.append((canvas_id, markdown))
            return {"ok": True}

    monkeypatch.setattr("slack_project.cli.sync_todo.SlackClient", FakeSlackClient)
    args = ["--project", "my-project"]
    if dry_run:
        args.append("--dry-run")
    result = main(args)
    assert result == 0
    return calls


def test_canvas_push_success(tmp_path, monkeypatch):
    _setup_project(tmp_path, "## 議事録由来タスク\n- [ ] A\n")
    calls = _run_canvas_push(tmp_path, monkeypatch)
    assert calls and calls[0][0] == "F456"


def test_canvas_push_excludes_fully_completed_sections(tmp_path, monkeypatch):
    todo_text = (
        "## 議事録由来タスク\n"
        "### 2026-05-15 定例\n"
        "- [x] 完了A\n"
        "- [x] 完了B\n"
        "### 進行中\n"
        "- [x] 進行済み\n"
        "- [ ] 進行中\n"
    )
    _setup_project(tmp_path, todo_text)
    calls = _run_canvas_push(tmp_path, monkeypatch)
    markdown = calls[0][1]
    assert "### 2026-05-15 定例" not in markdown
    assert "### 進行中" in markdown
    assert "- [ ] 進行中" in markdown


def test_canvas_push_keeps_partially_completed_sections(tmp_path, monkeypatch):
    todo_text = (
        "## 議事録由来タスク\n"
        "### A\n"
        "- [x] done\n"
        "- [ ] todo\n"
    )
    _setup_project(tmp_path, todo_text)
    calls = _run_canvas_push(tmp_path, monkeypatch)
    markdown = calls[0][1]
    assert "### A" in markdown
    assert "- [ ] todo" in markdown


def test_canvas_push_empty_todo_sends_header_only(tmp_path, monkeypatch):
    _setup_project(tmp_path, "## 議事録由来タスク\n")
    calls = _run_canvas_push(tmp_path, monkeypatch)
    assert calls[0][1] == "## 議事録由来タスク\n"


def test_canvas_push_dry_run_excludes_completed_sections(tmp_path, monkeypatch, capsys):
    todo_text = (
        "## 議事録由来タスク\n"
        "### 完了\n"
        "- [x] 完了A\n"
        "### 進行中\n"
        "- [ ] 進行中\n"
    )
    _setup_project(tmp_path, todo_text)
    calls = _run_canvas_push(tmp_path, monkeypatch, dry_run=True)
    markdown = calls[0][1]
    assert "### 完了" not in markdown
    assert "### 進行中" in markdown
    captured = capsys.readouterr()
    assert "dry-run" in captured.out
