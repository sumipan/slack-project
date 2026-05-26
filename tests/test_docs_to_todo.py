from __future__ import annotations

import pytest
from slack_project.docs.parser import ParsedMinutes, Task
from slack_project.docs.to_todo import extract_tasks, build_todo_section, TodoItem


def _make_parsed(tasks: list[Task]) -> ParsedMinutes:
    return ParsedMinutes(
        title="テスト会議",
        participants="太郎, 花子",
        overview="概要",
        body_text="",
        tasks=tasks,
    )


def _make_task(summary: str, assignees: list[str], due_date: str | None = None) -> Task:
    return Task(
        summary=summary,
        assignees=assignees,
        due_date=due_date,
        description=None,
        raw_line=f"- [ ] {summary}",
    )


def test_extract_tasks_converts_to_todo_items():
    task = _make_task("レビュー", ["太郎"], "2026-03-01")
    parsed = _make_parsed([task])
    items = extract_tasks(parsed)
    assert len(items) == 1
    assert isinstance(items[0], TodoItem)
    assert items[0].assignee == "太郎"
    assert items[0].content == "レビュー"
    assert items[0].due == "2026-03-01"


def test_extract_tasks_multiple_assignees_first_only():
    task = _make_task("確認", ["太郎", "花子"])
    items = extract_tasks(_make_parsed([task]))
    assert items[0].assignee == "太郎"


def test_extract_tasks_no_assignees():
    task = _make_task("宿題", [])
    items = extract_tasks(_make_parsed([task]))
    assert items[0].assignee == "未割り当て"


def test_extract_tasks_empty():
    items = extract_tasks(_make_parsed([]))
    assert items == []


def test_build_todo_section_header():
    items = [TodoItem(assignee="太郎", content="レビュー", due="2026-03-01")]
    section = build_todo_section("2026-01-15", "定例", items, "議事録/2026-01-15_定例.md")
    assert section.startswith("### 2026-01-15 定例")


def test_build_todo_section_source_comment():
    items = [TodoItem(assignee="太郎", content="レビュー", due=None)]
    section = build_todo_section("2026-01-15", "定例", items, "議事録/2026-01-15_定例.md")
    assert "<!-- 出典: 議事録/2026-01-15_定例.md -->" in section


def test_build_todo_section_task_lines():
    items = [
        TodoItem(assignee="太郎", content="レビュー", due="2026-03-01"),
        TodoItem(assignee="花子", content="デプロイ", due=None),
    ]
    section = build_todo_section("2026-01-15", "定例", items, "source.md")
    assert "- [ ]" in section
    assert "レビュー" in section
    assert "デプロイ" in section


def test_build_todo_section_empty_tasks():
    section = build_todo_section("2026-01-15", "定例", [], "source.md")
    assert "### 2026-01-15 定例" in section
    assert "<!-- 出典: source.md -->" in section
    assert "- [ ]" not in section
