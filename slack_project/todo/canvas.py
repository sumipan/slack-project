"""
slack_project.todo.canvas — todo.md から Canvas への片方向同期
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from slack_project.config_loader import get_slack_token, load_project_config
from slack_project.todo.parser import parse_todo_tasks


class ProjectWorkspace(Protocol):
    project_root: Path


def build_canvas_markdown(todo_text: str) -> str:
    """未完了タスクを含むセクションだけを抽出した Markdown を返す。"""
    tasks = parse_todo_tasks(todo_text)
    if not tasks:
        return "## 議事録由来タスク\n"

    section_tasks: dict[str | None, list[tuple[str, bool]]] = {}
    for raw_line, completed, _norm, _assignee, _due, section_key in tasks:
        section_tasks.setdefault(section_key, []).append((raw_line, completed))

    lines: list[str] = ["## 議事録由来タスク"]

    if None in section_tasks:
        for raw_line, _completed in section_tasks[None]:
            lines.append(raw_line)

    for section_key, rows in section_tasks.items():
        if section_key is None:
            continue
        if not rows:
            continue
        if all(completed for _raw, completed in rows):
            continue
        lines.append(f"### {section_key}")
        for raw_line, _completed in rows:
            lines.append(raw_line)

    return "\n".join(lines).rstrip() + "\n"


def push_to_canvas(
    workspace: ProjectWorkspace,
    project: str,
    *,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """todo.md の内容を Slack Canvas に push する。"""
    project_root = workspace.project_root
    todo_path = project_root / "todo.md"
    if not todo_path.exists():
        return False, f"todo.md が存在しません: {todo_path}"

    markdown = build_canvas_markdown(todo_path.read_text(encoding="utf-8"))
    if dry_run:
        return True, f"dry-run: Canvas へ push 予定です ({project})"

    config = load_project_config(project_root)
    slack = config.get("slack") or {}
    token = get_slack_token(config)
    canvas_id = (slack.get("todo_canvas_id") or "").strip()

    if not canvas_id:
        return False, "slack.todo_canvas_id が未設定です。config.yaml に追加してください。"
    if not token:
        return False, "Slack の user_token が未設定です。config.yaml に追加してください。"

    try:
        import requests

        payload = {
            "canvas_id": canvas_id,
            "changes": [
                {
                    "operation": "replace",
                    "document_range": {
                        "anchor_block": {"id": "start"},
                        "end_block": {"id": "end"},
                    },
                    "elements": [{"type": "markdown", "text": markdown}],
                }
            ],
        }
        response = requests.post(
            "https://slack.com/api/canvases.edit",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            return False, f"Slack API エラー: {data.get('error', 'unknown')}"
        return True, f"Canvas を更新しました: {project}"
    except Exception as exc:
        return False, str(exc)
