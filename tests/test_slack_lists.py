"""tests/test_slack_lists.py — slack_project.slack.lists の単体テスト"""
from __future__ import annotations

from unittest.mock import MagicMock

from slack_project.slack.lists import (
    _slack_lists_items_list_page,
    _get_primary_text_column_id,
    list_entries,
    add_entry,
    update_entry_status,
)


def _make_client(resp_dict: dict) -> MagicMock:
    client = MagicMock()
    client.api_call.return_value = resp_dict
    return client


class TestSlackListsItemsListPage:
    def test_single_page(self):
        """TC#1: 1ページ分のレスポンスでアイテムと next_cursor=None が返る"""
        items_data = [{"id": "I1", "fields": []}, {"id": "I2", "fields": []}]
        resp = {"ok": True, "items": items_data, "response_metadata": {"next_cursor": ""}}
        client = _make_client(resp)
        items, cursor = _slack_lists_items_list_page(client, "L1")
        assert len(items) == 2
        assert cursor is None

    def test_pagination(self):
        """TC#2: 2ページ分のレスポンスで全アイテムが取得できる（list_entries 経由）"""
        page1 = {
            "ok": True,
            "items": [{"id": "I1", "fields": [{"text": "タスク1", "column_id": "c1"}]}],
            "response_metadata": {"next_cursor": "cursor_abc"},
        }
        page2 = {
            "ok": True,
            "items": [{"id": "I2", "fields": [{"text": "タスク2", "column_id": "c1"}]}],
            "response_metadata": {"next_cursor": ""},
        }
        client = MagicMock()
        client.api_call.side_effect = [page1, page2]
        entries = list_entries(client, "L1")
        assert len(entries) == 2
        assert entries[0][0] == "タスク1"
        assert entries[1][0] == "タスク2"

    def test_api_error_returns_empty(self):
        """API エラー時は空リストと None を返す"""
        resp = {"ok": False, "error": "not_allowed"}
        client = _make_client(resp)
        items, cursor = _slack_lists_items_list_page(client, "L1")
        assert items == []
        assert cursor is None


class TestAddEntry:
    def test_success_returns_item(self):
        """TC#3: 正常レスポンスで作成されたアイテム dict が返る"""
        resp = {"ok": True, "item": {"id": "I_NEW", "fields": []}}
        client = _make_client(resp)
        result = add_entry(
            client, "L1", "新タスク", False,
            primary_text_column_id="col_text",
            assignee_column_id=None, assignee_slack_id=None,
            due_date_column_id=None, due_iso=None,
        )
        assert result.get("id") == "I_NEW"

    def test_api_error_returns_empty_dict(self):
        """TC#4: API エラー時は空 dict が返る"""
        resp = {"ok": False, "error": "invalid_list"}
        client = _make_client(resp)
        result = add_entry(
            client, "L1", "タスク", False,
            primary_text_column_id="col_text",
            assignee_column_id=None, assignee_slack_id=None,
            due_date_column_id=None, due_iso=None,
        )
        assert result == {}


class TestUpdateEntryStatus:
    def test_update_checked_returns_data(self):
        """TC#5: 正常レスポンスでデータ dict が返る"""
        resp = {"ok": True, "item": {"id": "I1"}}
        client = _make_client(resp)
        result = update_entry_status(client, "L1", "I1", "col_status", checked=True)
        assert isinstance(result, dict)

    def test_missing_status_column_returns_empty(self):
        """status_column_id が空のとき空 dict を返し API 未呼び出し"""
        client = MagicMock()
        result = update_entry_status(client, "L1", "I1", "", checked=True)
        assert result == {}
        client.api_call.assert_not_called()


class TestGetPrimaryTextColumnId:
    def test_returns_column_id_from_items(self):
        """TC#6: items に rich_text フィールドがあれば column_id を返す"""
        items_resp = {
            "ok": True,
            "items": [
                {
                    "id": "I1",
                    "fields": [
                        {"column_id": "col_primary", "rich_text": [{"type": "rich_text"}]},
                    ],
                }
            ],
            "response_metadata": {"next_cursor": ""},
        }
        client = _make_client(items_resp)
        cid = _get_primary_text_column_id(client, "L1")
        assert cid == "col_primary"

    def test_returns_none_when_no_columns(self):
        """アイテムもスキーマも空の場合 None を返す"""
        resp_empty = {"ok": True, "items": [], "response_metadata": {"next_cursor": ""}}
        resp_schema_error = {"ok": False}
        client = MagicMock()
        client.api_call.side_effect = [resp_empty, resp_schema_error, resp_schema_error]
        cid = _get_primary_text_column_id(client, "L1")
        assert cid is None


class TestImport:
    def test_import_from_module(self):
        from slack_project.slack.lists import list_entries, add_entry, update_entry_status
        assert callable(list_entries)
        assert callable(add_entry)
        assert callable(update_entry_status)
