from __future__ import annotations

import pytest
from slack_project.docs.parser import Task
from slack_project.docs.formatter import (
    format_head_blocks,
    format_body_blocks,
    format_action_blocks,
    fallback_text,
)


def _make_task(summary: str, assignees: list[str], due_date: str | None = None) -> Task:
    return Task(
        summary=summary,
        assignees=assignees,
        due_date=due_date,
        description=None,
        raw_line=f"- [ ] {'・'.join(assignees)}：{summary}",
    )


def test_format_head_blocks_structure():
    blocks = format_head_blocks("概要テキスト", "会議名", "A, B")
    types = [b["type"] for b in blocks]
    assert "section" in types
    assert "context" in types


def test_format_head_blocks_no_participants():
    blocks = format_head_blocks("概要", "会議名", "")
    types = [b["type"] for b in blocks]
    assert "context" not in types


def test_format_body_blocks_empty_body():
    blocks = format_body_blocks("会議名", "")
    assert any(b["type"] == "header" for b in blocks)


def test_format_action_blocks_with_members_map():
    task = _make_task("レビュー 2026-03-01", ["太郎"], "2026-03-01")
    blocks = format_action_blocks([task], {"太郎": "U1234"})
    text = blocks[0]["text"]["text"]
    assert "<@U1234>" in text


def test_format_action_blocks_no_members_map():
    task = _make_task("レビュー", ["太郎"])
    blocks = format_action_blocks([task], None)
    text = blocks[0]["text"]["text"]
    assert "太郎" in text
    assert "<@" not in text


def test_format_action_blocks_empty():
    blocks = format_action_blocks([], None)
    assert len(blocks) > 0
    assert blocks[0]["type"] == "section"


def test_format_action_blocks_uid_not_found():
    task = _make_task("確認", ["花子"])
    blocks = format_action_blocks([task], {"太郎": "U9999"})
    text = blocks[0]["text"]["text"]
    assert "花子" in text


def test_section_text_max_3000():
    long_content = "あ" * 3100
    blocks = format_body_blocks("会議名", f"## 詳細\n### 見出し\n{long_content}")
    for b in blocks:
        if b.get("type") == "section" and isinstance(b.get("text"), dict):
            assert len(b["text"].get("text", "")) <= 3000


def test_fallback_text_max_100():
    blocks = format_head_blocks("あ" * 200, "会議名", "参加者")
    result = fallback_text(blocks)
    assert len(result) <= 101


def test_fallback_text_short_input():
    blocks = format_head_blocks("短い概要", "会議名", "")
    result = fallback_text(blocks)
    assert "会議名" in result or "短い概要" in result
