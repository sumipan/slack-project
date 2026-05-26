"""
slack_project.todo.parser — TODO Markdown のパース・テキスト正規化

純粋関数群。外部 I/O を持たない。
"""
from __future__ import annotations

import re
from datetime import datetime

RE_TASK_LINE = re.compile(r"^(\s*[-*]\s+)\[([ xX])\]\s+(.+)$")

RE_TRAILING_META = re.compile(
    r"\s*([（(]\s*担当\s*[：:]\s*[^）)]+\s*[）)]\s*)?(\d{2,4}-\d{2}(-\d{2})?)?\s*$"
)

RE_DUE_YYYY_MM_DD = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
RE_DUE_MM_DD = re.compile(r"(?:^|[\s（(])(\d{1,2})-(\d{1,2})(?:[\s）)]|$)")
RE_DUE_JP = re.compile(r"(\d{1,2})月(\d{1,2})日")

RE_ASSIGNEE_PAREN = re.compile(r"[（(]\s*担当\s*[：:]\s*([^）)]+)\s*[）)]")


def normalize_task_text(text: str) -> str:
    """末尾メタデータ（担当・日付）を除去した正規化テキストを返す。"""
    t = (text or "").strip()
    t = RE_TRAILING_META.sub("", t).strip()
    return t


def parse_due_date(text: str) -> str | None:
    """タスクテキストから日付を抽出し ISO 形式 (YYYY-MM-DD) で返す。
    対応フォーマット: YYYY-MM-DD, MM-DD, 日本語（〜月〜日）。
    該当なしは None。"""
    if not (text or "").strip():
        return None
    t = text.strip()
    year = datetime.now().year
    m = RE_DUE_YYYY_MM_DD.search(t)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    m = RE_DUE_MM_DD.search(t)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{year:04d}-{mo:02d}-{d:02d}"
    m = RE_DUE_JP.search(t)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{year:04d}-{mo:02d}-{d:02d}"
    return None


def parse_assignee(body: str) -> str | None:
    """'(担当: name)' または 'name:' 形式から担当者名を抽出。該当なしは None。"""
    if not (body or "").strip():
        return None
    text = body.strip()
    m = RE_ASSIGNEE_PAREN.search(text)
    if m:
        return m.group(1).strip() or None
    if "：" in text:
        before, _ = text.split("：", 1)
        if before and before.strip():
            return before.strip()
    return None


def resolve_assignee_to_slack_id(name: str, members: dict[str, str]) -> str | None:
    """担当者名を members マッピングで Slack user ID に解決。"""
    n = (name or "").strip()
    uid = (members or {}).get(n)
    if isinstance(uid, str) and uid.strip().upper().startswith("U"):
        return uid.strip()
    return None


def parse_todo_tasks(todo_text: str) -> list[tuple[str, bool, str, str | None, str | None]]:
    """todo.md の '議事録由来タスク' セクションをパースし、
    [(raw_line, completed, normalized_text, assignee_name, due_iso)] を返す。"""
    if not todo_text:
        return []
    in_section = False
    result: list[tuple[str, bool, str, str | None, str | None]] = []
    for line in todo_text.split("\n"):
        if line.strip().startswith("## ") and "議事録由来タスク" in line:
            in_section = True
            continue
        if in_section and line.strip().startswith("## "):
            break
        if not in_section:
            continue
        m = RE_TASK_LINE.match(line)
        if m:
            check, body = m.group(2), m.group(3)
            completed = check.lower() == "x"
            normalized = normalize_task_text(body)
            assignee = parse_assignee(body)
            due_iso = parse_due_date(body)
            result.append((line.strip(), completed, normalized, assignee, due_iso))
    return result
