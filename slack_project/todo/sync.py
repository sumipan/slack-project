"""
slack_project.todo.sync — todo.md ↔ Slack Lists 双方向同期

公開 API:
    run(project, *, fetch_only, check_only, dry_run) -> tuple[bool, str]
"""
from __future__ import annotations

import json
from pathlib import Path

from slack_project.todo import parser as _parser


# ---------------------------------------------------------------------------
# 内部関数
# ---------------------------------------------------------------------------


def parse_list_entries_from_cache(cache_path: Path) -> list[tuple[str, bool, str]]:
    """JSON キャッシュからエントリを復元。"""
    if not cache_path.exists():
        return []
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        entries = data.get("entries") or []
        return [
            (e.get("title") or e.get("content") or "", e.get("checked", False), e.get("id"))
            for e in entries
        ]
    except (json.JSONDecodeError, OSError):
        return []


def write_entries_cache(entries: list, cache_path: Path) -> None:
    """エントリを JSON キャッシュに永続化。"""
    payload = {
        "entries": [
            {"title": body, "checked": completed, "id": eid}
            for body, completed, eid in entries
        ]
    }
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def apply_list_to_todo(todo_path: Path, entries: list) -> None:
    """List の完了状態を todo.md に反映。"""
    if not entries:
        return
    list_checked = {
        _parser.normalize_task_text(body)
        for body, completed, _ in entries
        if completed
    }
    if not list_checked:
        return
    text = todo_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    in_section = False
    new_lines: list[str] = []
    for line in lines:
        if line.strip().startswith("## ") and "議事録由来タスク" in line:
            in_section = True
            new_lines.append(line)
            continue
        if in_section and line.strip().startswith("## "):
            in_section = False
            new_lines.append(line)
            continue
        if not in_section:
            new_lines.append(line)
            continue
        m = _parser.RE_TASK_LINE.match(line)
        if m:
            check, body = m.group(2), m.group(3)
            norm = _parser.normalize_task_text(body)
            if norm in list_checked and check.lower() != "x":
                new_lines.append(line.replace("- [ ]", "- [x]", 1))
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    todo_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def build_entries_for_list(
    todo_tasks: list,
    existing_entries: list,
) -> list:
    """todo.md タスクと既存エントリをマージ。完了済み [x] の新規追加は除外。"""
    seen: set[str] = set()
    out: list[tuple[str, bool, str | None]] = []
    todo_by_norm = {norm: completed for (_, completed, norm, _, _) in todo_tasks}
    for body, completed, entry_id in existing_entries:
        norm = _parser.normalize_task_text(body)
        seen.add(norm)
        completed = todo_by_norm.get(norm, completed)
        out.append((body, completed, entry_id))
    for raw_line, completed, norm, _assignee, _due in todo_tasks:
        if norm in seen:
            continue
        if completed:
            continue
        seen.add(norm)
        out.append((norm, completed, None))
    return out


def _resolve_slack_lists_module(slack_lists):
    """slack_lists モジュールを返す。未指定時は tools.project.slack_lists を import する。"""
    if slack_lists is not None:
        return slack_lists, None
    try:
        from tools.project import slack_lists as _sl
        return _sl, None
    except ImportError:
        return None, "slack_lists モジュールが見つかりません。slack_lists を引数で渡してください。"


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


def run(
    project: str,
    *,
    fetch_only: bool = False,
    check_only: bool = False,
    dry_run: bool = False,
    project_root: Path | None = None,
    load_config=None,
    get_token=None,
    slack_lists=None,
) -> tuple[bool, str]:
    """
    Slack List と todo.md を同期する。

    Args:
        project: プロジェクト名（例: craftsake）
        fetch_only: True の場合、Slack → todo.md 方向のみ
        check_only: True の場合、不一致を検出・表示するのみ（書き込みなし）
        dry_run: True の場合、書き込みを行わず動作確認のみ
        project_root: プロジェクトルートパス（省略時は config から解決）
        load_config: 設定ローダー関数（省略時は slack_project.config を使用）
        get_token: トークン取得関数（省略時は slack_project.config を使用）
        slack_lists: slack_lists モジュール（省略時は tools.project.slack_lists を参照）

    Returns:
        (success: bool, message: str)
    """
    messages: list[str] = []

    # プロジェクトパス解決
    if project_root is None:
        project_arg = (project or "").strip().replace("\\", "/")
        if project_arg.startswith("projects/"):
            parts = project_arg.split("/")
            project_name = parts[1] if len(parts) > 1 else parts[0]
        else:
            project_name = project_arg.rstrip("/")

        try:
            from pathlib import Path as _Path
            import os
            repo_root = _Path(os.environ.get("REPO_ROOT", Path(__file__).resolve().parent.parent.parent.parent))
            project_root = repo_root / "projects" / project_name
        except Exception:
            return False, "project_root を特定できません。project_root を引数で渡してください。"
    else:
        project_name = project_root.name

    if not project_root.is_dir():
        return False, f"プロジェクトフォルダが存在しません: {project_root}"

    todo_path = project_root / "todo.md"
    if not todo_path.exists():
        return False, f"todo.md が存在しません: {todo_path}"

    if load_config is None or get_token is None:
        try:
            from tools.project.config_loader import (
                load_project_config as _load,
                get_slack_token as _get_token,
            )
            if load_config is None:
                load_config = _load
            if get_token is None:
                get_token = _get_token
        except ImportError:
            return False, "設定ローダーが見つかりません。load_config / get_token を引数で渡してください。"

    try:
        config = load_config(project_root)
    except Exception as e:
        return False, f"config の読み込みに失敗しました: {e}"

    slack = config.get("slack") or {}
    list_id = (slack.get("list_id") or slack.get("task_list_id") or "").strip() or None
    token = get_token(config)
    cache_path = project_root / "slack_list_entries_cache.json"

    # --- (1) List の最新取得 ---
    list_entries: list[tuple[str, bool, str | None]] = []

    if token and list_id:
        slack_lists, err = _resolve_slack_lists_module(slack_lists)
        if err:
            return False, err
        try:
            from slack_sdk import WebClient
            client = WebClient(token=token)
            raw = slack_lists.list_entries(client, list_id)
            list_entries = raw
            if list_entries and not check_only and not dry_run:
                write_entries_cache(list_entries, cache_path)
                messages.append("Slack List を API から取得し、キャッシュを更新しました。")
            elif list_entries:
                messages.append("Slack List を API から取得しました（チェックのみ）。")
        except ImportError:
            return False, "slack_sdk がインストールされていません: pip install slack_sdk"
        except Exception as e:
            list_entries = parse_list_entries_from_cache(cache_path)
            err_msg = str(e)
            if "unknown_method" in err_msg:
                messages.append(
                    "Slack の公開 Web API に slackLists.items.list が存在しません（unknown_method）。"
                )
            if not list_entries and not fetch_only and not check_only and not dry_run:
                return False, f"Slack Lists API の取得に失敗しました: {e}"
    else:
        list_entries = parse_list_entries_from_cache(cache_path)

    todo_text = todo_path.read_text(encoding="utf-8")
    tasks = _parser.parse_todo_tasks(todo_text)

    # --- check_only モード ---
    if check_only:
        list_norms = {_parser.normalize_task_text(body) for body, _, _ in list_entries}
        list_completed = {
            _parser.normalize_task_text(body)
            for body, completed, _ in list_entries
            if completed
        }
        todo_norms = {norm for _, _, norm, _, _ in tasks}
        todo_completed = {norm for _, completed, norm, _, _ in tasks if completed}

        only_in_todo = [norm for _, completed, norm, _, _ in tasks if norm not in list_norms and not completed]
        only_in_list = [body for body, _, _ in list_entries if _parser.normalize_task_text(body) not in todo_norms]
        status_mismatch = [
            norm for norm in list_norms & todo_norms
            if (norm in list_completed) != (norm in todo_completed)
        ]

        lines: list[str] = [f"【チェック結果】project={project_name}"]
        if not only_in_todo and not only_in_list and not status_mismatch:
            lines.append("不一致なし: todo.md と Slack List は同期されています。")
        else:
            if only_in_todo:
                lines.append(f"\ntodo.md のみ（未追加: {len(only_in_todo)} 件）:")
                for t in only_in_todo:
                    lines.append(f"  + {t}")
            if only_in_list:
                lines.append(f"\nSlack List のみ（todo.md にない: {len(only_in_list)} 件）:")
                for t in only_in_list:
                    lines.append(f"  - {t}")
            if status_mismatch:
                lines.append(f"\n完了状態の不一致（{len(status_mismatch)} 件）:")
                for t in status_mismatch:
                    todo_done = t in todo_completed
                    list_done = t in list_completed
                    lines.append(
                        f"  ! {t}  (todo={'完了' if todo_done else '未完了'}, "
                        f"list={'完了' if list_done else '未完了'})"
                    )
        return True, "\n".join(lines)

    # --- dry_run モード ---
    if dry_run:
        list_checked = {
            _parser.normalize_task_text(body)
            for body, completed, _ in list_entries
            if completed
        }
        list_norms = {_parser.normalize_task_text(body) for body, _, _ in list_entries}

        would_complete = [
            norm for _, todo_done, norm, _, _ in tasks
            if not todo_done and norm in list_checked
        ]
        would_add = [
            norm for _, todo_done, norm, _, _ in tasks
            if not todo_done and norm not in list_norms
        ]

        lines = [f"【dry-run】同期プレビュー: project={project_name}"]
        lines.append(f"\nSlack → todo.md（完了反映）: {len(would_complete)} 件")
        for t in would_complete:
            lines.append(f"  ✓ {t}")
        lines.append(f"\ntodo.md → Slack List（新規追加）: {len(would_add)} 件")
        for t in would_add:
            lines.append(f"  + {t}")
        if not would_complete and not would_add:
            lines.append("変更なし: 同期不要です。")
        lines.append("\n（実際に実行するには --dry-run を外してください）")
        return True, "\n".join(lines)

    # --- 通常同期モード ---
    if list_entries:
        apply_list_to_todo(todo_path, list_entries)
        messages.append("List の完了状態を todo.md に反映しました。")
    else:
        if fetch_only and not cache_path.exists():
            messages.append("List のキャッシュがありません。list_id を設定し、通常実行で 1 回同期してください。")
        elif not list_id:
            messages.append("slack.list_id が未設定です。config.yaml に slack.list_id を追加してください。")

    if fetch_only:
        return True, "\n".join(messages)

    if not list_id:
        return False, "slack.list_id が未設定です。config.yaml に追加してください。"
    if not token:
        return False, (
            "Slack の user_token が未設定です。config_local.yml に slack.user_token を設定してください。"
        )

    try:
        from slack_sdk import WebClient
    except ImportError:
        return False, "slack_sdk がインストールされていません: pip install slack_sdk"

    client = WebClient(token=token)

    raw_members = config.get("members") or {}
    if isinstance(raw_members, list):
        members_map: dict[str, str] = {
            m["name"]: m["slack_id"] for m in raw_members if "name" in m and "slack_id" in m
        }
    elif isinstance(raw_members, dict):
        members_map = raw_members
    else:
        members_map = {}

    slack_lists, err = _resolve_slack_lists_module(slack_lists)
    if err:
        return False, err

    status_cid, assignee_cid, due_cid, primary_cid = slack_lists.get_column_ids(
        client, list_id, config
    )

    norm_to_assignee_due = {norm: (assignee, due_iso) for (_, _, norm, assignee, due_iso) in tasks}

    merged = build_entries_for_list(tasks, list_entries)
    added = 0

    for body, completed, entry_id in merged:
        if entry_id is None:
            assignee_name, due_date_iso = norm_to_assignee_due.get(body, (None, None))
            assignee_slack_id = (
                _parser.resolve_assignee_to_slack_id(assignee_name, members_map)
                if assignee_name
                else None
            )
            item = slack_lists.add_entry(
                client,
                list_id,
                body,
                completed,
                primary_cid,
                assignee_cid,
                assignee_slack_id,
                due_cid,
                due_date_iso,
            )
            if item:
                added += 1

    refreshed = slack_lists.list_entries(client, list_id)
    if refreshed:
        write_entries_cache(refreshed, cache_path)

    messages.append(f"Slack List を更新しました（追加: {added} 件）。")
    return True, "\n".join(messages)


__all__ = ["run"]
