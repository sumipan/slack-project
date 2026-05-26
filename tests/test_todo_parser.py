from datetime import datetime

import pytest

from slack_project.todo.parser import (
    normalize_task_text,
    parse_assignee,
    parse_due_date,
    parse_todo_tasks,
    resolve_assignee_to_slack_id,
)

CURRENT_YEAR = datetime.now().year


# ---------------------------------------------------------------------------
# parse_todo_tasks
# ---------------------------------------------------------------------------


def test_parse_todo_tasks_basic():
    text = "## 議事録由来タスク\n- [ ] タスクA\n- [x] タスクB\n"
    result = parse_todo_tasks(text)
    assert len(result) == 2
    _, done_a, norm_a, _, _ = result[0]
    _, done_b, norm_b, _, _ = result[1]
    assert done_a is False
    assert done_b is True
    assert norm_a == "タスクA"
    assert norm_b == "タスクB"


def test_parse_todo_tasks_empty():
    assert parse_todo_tasks("") == []


def test_parse_todo_tasks_no_section():
    text = "## 無関係セクション\n- [ ] タスク\n"
    assert parse_todo_tasks(text) == []


def test_parse_todo_tasks_multiple():
    text = "## 議事録由来タスク\n- [ ] A\n- [x] B\n- [ ] C\n"
    result = parse_todo_tasks(text)
    assert len(result) == 3


def test_parse_todo_tasks_stops_at_next_section():
    text = "## 議事録由来タスク\n- [ ] A\n## 他のセクション\n- [ ] B\n"
    result = parse_todo_tasks(text)
    assert len(result) == 1
    assert result[0][2] == "A"


def test_parse_todo_tasks_nested_list_ignored():
    text = "## 議事録由来タスク\n- [ ] A\n  - 詳細\n"
    result = parse_todo_tasks(text)
    assert len(result) == 1


def test_parse_todo_tasks_returns_raw_line():
    text = "## 議事録由来タスク\n- [ ] タスクA\n"
    result = parse_todo_tasks(text)
    assert result[0][0] == "- [ ] タスクA"


# ---------------------------------------------------------------------------
# normalize_task_text
# ---------------------------------------------------------------------------


def test_normalize_removes_assignee_and_date():
    assert normalize_task_text("タスク（担当: 太郎）2025-06-01") == "タスク"


def test_normalize_plain_text():
    assert normalize_task_text("タスク") == "タスク"


def test_normalize_none():
    assert normalize_task_text(None) == ""


def test_normalize_empty():
    assert normalize_task_text("") == ""


# ---------------------------------------------------------------------------
# parse_due_date
# ---------------------------------------------------------------------------


def test_parse_due_date_yyyy_mm_dd():
    assert parse_due_date("タスク 2025-06-15") == "2025-06-15"


def test_parse_due_date_jp():
    assert parse_due_date("タスク 6月15日") == f"{CURRENT_YEAR}-06-15"


def test_parse_due_date_none_when_empty():
    assert parse_due_date("") is None


def test_parse_due_date_none_when_no_date():
    assert parse_due_date("日付なしのテキスト") is None


def test_parse_due_date_none_when_none():
    # None は渡せないが空文字として扱われることを期待
    assert parse_due_date("") is None


# ---------------------------------------------------------------------------
# parse_assignee
# ---------------------------------------------------------------------------


def test_parse_assignee_paren_form():
    assert parse_assignee("（担当: 太郎）タスク内容") == "太郎"


def test_parse_assignee_colon_form():
    assert parse_assignee("太郎：タスク内容") == "太郎"


def test_parse_assignee_none_when_empty():
    assert parse_assignee("") is None


def test_parse_assignee_none_when_no_match():
    assert parse_assignee("ただのテキスト") is None


# ---------------------------------------------------------------------------
# resolve_assignee_to_slack_id
# ---------------------------------------------------------------------------


def test_resolve_assignee_found():
    assert resolve_assignee_to_slack_id("太郎", {"太郎": "U12345"}) == "U12345"


def test_resolve_assignee_not_found():
    assert resolve_assignee_to_slack_id("不明", {"太郎": "U12345"}) is None


def test_resolve_assignee_empty_dict():
    assert resolve_assignee_to_slack_id("太郎", {}) is None
