from __future__ import annotations

from dataclasses import dataclass

from slack_project.docs.parser import ParsedMinutes


@dataclass
class TodoItem:
    assignee: str
    content: str
    due: str | None


def extract_tasks(parsed: ParsedMinutes) -> list[TodoItem]:
    """ParsedMinutes.tasks を TodoItem リストに変換する。
    複数担当者がいる場合は先頭を assignee に設定。担当者なしは '未割り当て'。"""
    return [
        TodoItem(
            assignee=t.assignees[0] if t.assignees else "未割り当て",
            content=t.summary,
            due=t.due_date,
        )
        for t in parsed.tasks
    ]


def build_todo_section(
    meeting_date: str,
    meeting_name: str,
    tasks: list[TodoItem],
    source_label: str,
) -> str:
    """todo.md 追記用の Markdown セクション文字列を返す。
    返り値例: '### 2026-01-15 定例\n<!-- 出典: ... -->\n- [ ] ...'"""
    lines = [
        f"### {meeting_date} {meeting_name}",
        f"<!-- 出典: {source_label} -->",
    ]
    for t in tasks:
        assignee_part = f"（担当: {t.assignee}）" if t.assignee else ""
        due_part = f" {t.due}" if t.due else ""
        lines.append(f"- [ ] {t.content}{assignee_part}{due_part}")
    return "\n".join(lines)
