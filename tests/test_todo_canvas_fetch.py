"""tests/test_todo_canvas_fetch.py — Canvas → local todo.md チェック反映の単体テスト"""
from __future__ import annotations

from slack_project.todo.canvas_fetch import (
    apply_check_states_to_local,
    parse_canvas_check_states,
)
from slack_project.todo.parser import MINUTES_SECTION


class TestParseCanvasCheckStates:
    def test_mixed_states(self):
        md = (
            "## 議事録由来タスク\n"
            "### 2026-01-01 A\n"
            "- [x] 完了タスク\n"
            "- [ ] 未完了タスク\n"
        )
        states = parse_canvas_check_states(md)
        assert states == {"完了タスク": True, "未完了タスク": False}

    def test_ignores_outside_section(self):
        md = (
            "# 別のドキュメント\n"
            "- [x] これは対象外\n"
            "\n"
            "## 議事録由来タスク\n"
            "### A\n"
            "- [x] 対象\n"
        )
        states = parse_canvas_check_states(md)
        assert states == {"対象": True}

    def test_empty_returns_empty(self):
        assert parse_canvas_check_states("") == {}

    def test_no_section_returns_empty(self):
        assert (
            parse_canvas_check_states("# heading\n- [x] task\n")
            == {}
        )

    def test_strips_trailing_meta_for_key(self):
        md = (
            "## 議事録由来タスク\n"
            "### A\n"
            "- [x] タスクA （担当: alice）\n"
        )
        states = parse_canvas_check_states(md)
        assert states == {"タスクA": True}

    def test_completed_wins_on_duplicate(self):
        md = (
            "## 議事録由来タスク\n"
            "### A\n"
            "- [ ] 同じタスク\n"
            "### B\n"
            "- [x] 同じタスク\n"
        )
        states = parse_canvas_check_states(md)
        assert states == {"同じタスク": True}


class TestApplyCheckStatesToLocal:
    def test_canvas_x_overrides_local_unchecked(self):
        local = (
            "## 議事録由来タスク\n"
            "### A\n"
            "- [ ] タスクA\n"
        )
        new_text, changed = apply_check_states_to_local(local, {"タスクA": True})
        assert "- [x] タスクA" in new_text
        assert changed == ["タスクA"]

    def test_local_x_is_preserved_when_canvas_unchecked(self):
        local = (
            "## 議事録由来タスク\n"
            "### A\n"
            "- [x] タスクA\n"
        )
        new_text, changed = apply_check_states_to_local(local, {"タスクA": False})
        assert "- [x] タスクA" in new_text
        assert changed == []

    def test_unknown_tasks_untouched(self):
        local = (
            "## 議事録由来タスク\n"
            "### A\n"
            "- [ ] タスクA\n"
            "- [ ] タスクB\n"
        )
        new_text, changed = apply_check_states_to_local(local, {"別タスク": True})
        assert "- [ ] タスクA" in new_text
        assert "- [ ] タスクB" in new_text
        assert changed == []

    def test_before_first_h2_not_modified(self):
        # #4083: import now covers every `##` section; only lines before the first `##` are skipped.
        local = (
            "# title\n"
            "- [ ] preamble task\n"
            "\n"
            f"## {MINUTES_SECTION}\n"
            "### A\n"
            "- [ ] target task\n"
        )
        new_text, changed = apply_check_states_to_local(
            local, {"preamble task": True, "target task": True}
        )
        assert "- [ ] preamble task" in new_text
        assert "- [x] target task" in new_text
        assert changed == ["target task"]

    def test_normalized_match_with_metadata(self):
        local = (
            "## 議事録由来タスク\n"
            "### A\n"
            "- [ ] タスクA （担当: alice）2026-03-15\n"
        )
        new_text, changed = apply_check_states_to_local(local, {"タスクA": True})
        assert "- [x] タスクA （担当: alice）2026-03-15" in new_text
        assert changed == ["タスクA"]

    def test_empty_local_returns_empty(self):
        new_text, changed = apply_check_states_to_local("", {"タスクA": True})
        assert new_text == ""
        assert changed == []

    def test_preserves_other_lines(self):
        local = (
            "## 議事録由来タスク\n"
            "### A\n"
            "メモ行\n"
            "- [ ] タスクA\n"
            "- [x] 既に完了\n"
        )
        new_text, _ = apply_check_states_to_local(local, {"タスクA": True})
        assert "メモ行" in new_text
        assert "- [x] 既に完了" in new_text


class TestMultipleSections:
    LOCAL = (
        "## A\n"
        "### sub-a\n"
        "- [ ] task a1\n"
        "\n"
        "## B\n"
        "### sub-b\n"
        "- [ ] task b1\n"
        "- [x] task b2\n"
    )
    CANVAS = (
        "## A\n"
        "### sub-a\n"
        "- [ ] task a1\n"
        "\n"
        "## B\n"
        "### sub-b\n"
        "- [x] task b1\n"
        "- [ ] task b2\n"
    )

    def test_parse_canvas_reads_all_sections(self):
        states = parse_canvas_check_states(self.CANVAS)
        assert states == {"task a1": False, "task b1": True, "task b2": False}

    def test_checked_in_section_b_is_imported(self):
        states = parse_canvas_check_states(self.CANVAS)
        new_text, changed = apply_check_states_to_local(self.LOCAL, states)
        assert "- [x] task b1" in new_text
        assert changed == ["task b1"]

    def test_unchecked_on_canvas_keeps_local_checked(self):
        states = parse_canvas_check_states(self.CANVAS)
        new_text, _ = apply_check_states_to_local(self.LOCAL, states)
        assert "- [x] task b2" in new_text
        assert "- [ ] task a1" in new_text
