from types import SimpleNamespace
from unittest.mock import MagicMock

from slack_project.todo.canvas import build_canvas_markdown, push_to_canvas
from slack_project.todo.parser import MINUTES_SECTION


def test_build_canvas_markdown_excludes_fully_completed_sections():
    todo_text = (
        "## 議事録由来タスク\n"
        "### 完了\n"
        "- [x] 完了A\n"
        "- [x] 完了B\n"
        "### 進行中\n"
        "- [x] 進行済み\n"
        "- [ ] 進行中\n"
    )
    rendered = build_canvas_markdown(todo_text)
    assert "### 完了" not in rendered
    assert "### 進行中" in rendered
    assert "- [ ] 進行中" in rendered


def test_build_canvas_markdown_keeps_partially_completed_sections():
    todo_text = (
        "## 議事録由来タスク\n"
        "### A\n"
        "- [x] done\n"
        "- [ ] todo\n"
    )
    rendered = build_canvas_markdown(todo_text)
    assert "### A" in rendered
    assert "- [ ] todo" in rendered


def test_push_to_canvas_dry_run_skips_api_call(tmp_path):
    project_root = tmp_path / "myproject"
    project_root.mkdir()
    (project_root / "todo.md").write_text("## 議事録由来タスク\n### A\n- [ ] a\n", encoding="utf-8")
    workspace = SimpleNamespace(project_root=project_root)

    success, message = push_to_canvas(workspace, "myproject", dry_run=True)

    assert success is True
    assert "dry-run" in message


def test_push_to_canvas_requires_canvas_id(tmp_path):
    project_root = tmp_path / "myproject"
    project_root.mkdir()
    (project_root / "todo.md").write_text("## 議事録由来タスク\n### A\n- [ ] a\n", encoding="utf-8")
    (project_root / "config.yaml").write_text("slack:\n  user_token: xoxp-test\n", encoding="utf-8")
    workspace = SimpleNamespace(project_root=project_root)

    success, message = push_to_canvas(workspace, "myproject", dry_run=False)

    assert success is False
    assert "todo_canvas_id" in message


def test_push_to_canvas_calls_slack_api(tmp_path, monkeypatch):
    project_root = tmp_path / "myproject"
    project_root.mkdir()
    (project_root / "todo.md").write_text("## 議事録由来タスク\n### A\n- [ ] a\n", encoding="utf-8")
    (project_root / "config.yaml").write_text(
        "slack:\n  user_token: xoxp-test\n  todo_canvas_id: F123\n",
        encoding="utf-8",
    )
    workspace = SimpleNamespace(project_root=project_root)

    post_mock = MagicMock(return_value=SimpleNamespace(json=lambda: {"ok": True}, raise_for_status=lambda: None))
    monkeypatch.setattr("requests.post", post_mock)

    success, _ = push_to_canvas(workspace, "myproject", dry_run=False)

    assert success is True
    assert post_mock.call_count == 1


MINUTES_ONLY_TODO = (
    "# todo\n"
    f"## {MINUTES_SECTION}\n"
    "- [ ] loose task\n"
    "### s1\n"
    "- [x] d1\n"
    "### s2\n"
    "- [x] d2\n"
    "- [ ] t2 (owner: alice) 2026-06-01\n"
)


def test_build_canvas_markdown_minutes_only_is_unchanged():
    expected = (
        f"## {MINUTES_SECTION}\n"
        "- [ ] loose task\n"
        "### s2\n"
        "- [x] d2\n"
        "- [ ] t2 (owner: alice) 2026-06-01\n"
    )
    assert build_canvas_markdown(MINUTES_ONLY_TODO) == expected


def test_build_canvas_markdown_empty_is_unchanged():
    assert build_canvas_markdown("") == f"## {MINUTES_SECTION}\n"
    assert build_canvas_markdown("# nothing\n") == f"## {MINUTES_SECTION}\n"


def test_build_canvas_markdown_multiple_sections():
    todo_text = (
        "## A\n"
        "### a-done\n"
        "- [x] a1\n"
        "### a-open\n"
        "- [ ] a2\n"
        "\n"
        "## B\n"
        "- [ ] b1\n"
        "### b-sub\n"
        "- [ ] b2\n"
    )
    rendered = build_canvas_markdown(todo_text)
    assert rendered == (
        "## A\n"
        "### a-open\n"
        "- [ ] a2\n"
        "\n"
        "## B\n"
        "- [ ] b1\n"
        "### b-sub\n"
        "- [ ] b2\n"
    )
