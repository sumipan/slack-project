"""slack_project.slack.lists — Slack Lists API 呼び出し・スキーマ解決・エントリ操作"""
from __future__ import annotations

import sys


def _resp_ok(resp) -> bool:
    if hasattr(resp, "get"):
        return bool(resp.get("ok", False))
    return False


def _resp_data(resp) -> dict:
    if isinstance(resp, dict):
        return resp
    if hasattr(resp, "get"):
        if hasattr(resp, "data") and isinstance(getattr(resp, "data", None), dict):
            return resp.data
        try:
            return dict(resp)
        except (TypeError, ValueError):
            pass
    return {}


def _slack_lists_items_list_page(
    client, list_id: str, cursor: str | None = None, limit: int = 100
) -> tuple[list[dict], str | None]:
    try:
        payload = {"list_id": list_id, "limit": limit}
        if cursor:
            payload["cursor"] = cursor
        resp = client.api_call("slackLists.items.list", json=payload)
        if not _resp_ok(resp):
            return ([], None)
        data = _resp_data(resp)
        items = data.get("items") or []
        meta = data.get("response_metadata") or {}
        next_cursor = (meta.get("next_cursor") or "").strip() or None
        return (items, next_cursor)
    except Exception:
        return ([], None)


def _parse_slack_list_item(item: dict) -> tuple[str, bool, str | None]:
    eid = item.get("id")
    fields = item.get("fields") or []
    title = ""
    checked = False
    for f in fields:
        if "text" in f and f["text"]:
            title = (f.get("text") or "").strip()
            if title:
                break
    if not title:
        for f in fields:
            v = f.get("value")
            if v is not None and not isinstance(v, bool) and str(v).strip():
                title = str(v).strip()
                break
    for f in fields:
        if "checkbox" in f and isinstance(f["checkbox"], list) and len(f["checkbox"]) > 0:
            checked = bool(f["checkbox"][0])
            break
    return (title or "(無題)", checked, eid)


def _get_list_schema(client, list_id: str) -> list[dict]:
    for method in ("slackLists.get", "lists.get"):
        try:
            resp = client.api_call(method, json={"list_id": list_id})
            if not _resp_ok(resp):
                continue
            data = _resp_data(resp)
            meta = data.get("list_metadata") or data.get("metadata") or data
            schema = meta.get("schema") or []
            if schema:
                return schema
        except Exception:
            continue
    return []


def _build_rich_text_initial_field(column_id: str, text: str) -> dict:
    return {
        "column_id": column_id,
        "rich_text": [
            {
                "type": "rich_text",
                "elements": [
                    {"type": "rich_text_section", "elements": [{"type": "text", "text": text}]}
                ],
            }
        ],
    }


def _get_status_column_id_from_items(items: list[dict], config_slack: dict) -> str | None:
    override = (config_slack.get("list_status_column_id") or "").strip()
    if override:
        return override
    for item in items:
        for f in item.get("fields") or []:
            if "checkbox" in f:
                cid = f.get("column_id") or f.get("key")
                if cid:
                    return cid
    return None


def _get_primary_text_column_id(client, list_id: str, config_slack: dict | None = None) -> str | None:
    config_slack = config_slack or {}
    items, _ = _slack_lists_items_list_page(client, list_id, limit=10)
    first_text_like_cid: str | None = None
    for item in items:
        for f in item.get("fields") or []:
            cid = f.get("column_id") or f.get("key")
            if not cid:
                continue
            if "checkbox" in f:
                continue
            if "user" in f or "date" in f:
                continue
            if first_text_like_cid is None:
                first_text_like_cid = cid
            if "text" in f and f.get("text") and isinstance(f.get("text"), str):
                return cid
            if "rich_text" in f:
                return cid
            v = f.get("value")
            if v is not None and not isinstance(v, bool) and str(v).strip():
                return cid
    if first_text_like_cid:
        return first_text_like_cid
    schema = _get_list_schema(client, list_id)
    for col in schema:
        cid = col.get("id") or col.get("column_id")
        if not cid:
            continue
        ctype = (col.get("type") or "").lower()
        if ctype in ("checkbox", "todo_completed"):
            continue
        if col.get("is_primary_column") or ctype in ("text", "rich_text"):
            return cid
    for col in schema:
        cid = col.get("id") or col.get("column_id")
        if cid and (col.get("type") or "").lower() not in ("checkbox", "todo_completed"):
            return cid
    override = (config_slack.get("primary_text_column_id") or "").strip()
    return override or None


def _get_assignee_and_due_column_ids(
    client, list_id: str, config_slack: dict
) -> tuple[str | None, str | None]:
    override_assignee = (config_slack.get("list_assignee_column_id") or "").strip()
    override_due = (config_slack.get("list_due_date_column_id") or "").strip()
    assignee_cid: str | None = override_assignee or None
    due_cid: str | None = override_due or None

    schema = _get_list_schema(client, list_id)
    for col in schema:
        cid = col.get("id") or col.get("column_id")
        if not cid:
            continue
        ctype = (col.get("type") or "").lower()
        if ctype in ("todo_assignee", "assignee") and not assignee_cid:
            assignee_cid = cid
        if ctype in ("todo_due_date", "due_date") and not due_cid:
            due_cid = cid

    if (assignee_cid is None or due_cid is None) and not (override_assignee and override_due):
        items, _ = _slack_lists_items_list_page(client, list_id, limit=50)
        for item in items:
            for f in item.get("fields") or []:
                key = (f.get("key") or "").strip().lower()
                cid = f.get("column_id")
                if not cid:
                    continue
                if not assignee_cid and (key in ("todo_assignee", "assignee") or "user" in f):
                    assignee_cid = cid
                if not due_cid and (key in ("todo_due_date", "due_date") or "date" in f):
                    due_cid = cid
            if assignee_cid and due_cid:
                break

    return (assignee_cid, due_cid)


def get_column_ids(
    client, list_id: str, config: dict
) -> tuple[str | None, str | None, str | None, str | None]:
    config_slack = config.get("slack") or config
    items, _ = _slack_lists_items_list_page(client, list_id, limit=10)
    status_cid = _get_status_column_id_from_items(items, config_slack)
    assignee_cid, due_cid = _get_assignee_and_due_column_ids(client, list_id, config_slack)
    primary_cid = _get_primary_text_column_id(client, list_id, config_slack)
    return (status_cid, assignee_cid, due_cid, primary_cid)


def list_entries(
    client, list_id: str, status_column_id: str | None = None
) -> list[tuple[str, bool, str | None]]:
    result: list[tuple[str, bool, str | None]] = []
    cursor = None
    while True:
        page, cursor = _slack_lists_items_list_page(client, list_id, cursor=cursor)
        for item in page:
            title, checked, eid = _parse_slack_list_item(item)
            result.append((title, checked, eid))
        if not cursor:
            break
    return result


def add_entry(
    client,
    list_id: str,
    text: str,
    checked: bool,
    primary_text_column_id: str | None,
    assignee_column_id: str | None,
    assignee_slack_id: str | None,
    due_date_column_id: str | None,
    due_iso: str | None,
) -> dict:
    col_id = primary_text_column_id
    try:
        if col_id:
            initial_fields = [_build_rich_text_initial_field(col_id, text)]
            resp = client.api_call(
                "slackLists.items.create",
                json={"list_id": list_id, "initial_fields": initial_fields},
            )
        else:
            resp = client.api_call("slackLists.items.create", json={"list_id": list_id})

        data = _resp_data(resp)
        if not _resp_ok(resp):
            err = data.get("error", "unknown")
            print(f"slackLists.items.create エラー: {err}", file=sys.stderr)
            return {}

        item = data.get("item") or (data.get("items") or [{}])[0]
        if not item:
            return {}

        row_id = item.get("id")

        if not col_id and row_id and text:
            col_id = _get_primary_text_column_id(client, list_id)
            if col_id:
                update_payload = {
                    "list_id": list_id,
                    "cells": [
                        {
                            "row_id": row_id,
                            "column_id": col_id,
                            "rich_text": [
                                {
                                    "type": "rich_text",
                                    "elements": [
                                        {
                                            "type": "rich_text_section",
                                            "elements": [{"type": "text", "text": text}],
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
                client.api_call("slackLists.items.update", json=update_payload)

        if row_id and (assignee_slack_id or due_iso):
            cells: list[dict] = []
            if assignee_slack_id and assignee_column_id:
                cells.append({
                    "row_id": row_id,
                    "column_id": assignee_column_id,
                    "user": [assignee_slack_id],
                })
            if due_iso and due_date_column_id:
                cells.append({
                    "row_id": row_id,
                    "column_id": due_date_column_id,
                    "date": [due_iso],
                })
            if cells:
                client.api_call(
                    "slackLists.items.update",
                    json={"list_id": list_id, "cells": cells},
                )

        return item

    except Exception as e:
        print(f"slackLists.items.create 例外: {e}", file=sys.stderr)
        return {}


def update_entry_status(
    client,
    list_id: str,
    item_id: str,
    status_column_id: str,
    checked: bool,
) -> dict:
    if not status_column_id:
        return {}
    try:
        payload = {
            "list_id": list_id,
            "cells": [{"row_id": item_id, "column_id": status_column_id, "checkbox": checked}],
        }
        resp = client.api_call("slackLists.items.update", json=payload)
        return _resp_data(resp)
    except Exception:
        return {}


def update_entry_metadata(
    client,
    list_id: str,
    item_id: str,
    assignee_column_id: str | None,
    assignee_slack_id: str | None,
    due_date_column_id: str | None,
    due_iso: str | None,
) -> dict:
    if not assignee_slack_id and not due_iso:
        return {}
    cells: list[dict] = []
    if assignee_slack_id and assignee_column_id:
        cells.append({"row_id": item_id, "column_id": assignee_column_id, "user": [assignee_slack_id]})
    if due_iso and due_date_column_id:
        cells.append({"row_id": item_id, "column_id": due_date_column_id, "date": [due_iso]})
    if not cells:
        return {}
    try:
        resp = client.api_call(
            "slackLists.items.update",
            json={"list_id": list_id, "cells": cells},
        )
        return _resp_data(resp)
    except Exception:
        return {}
