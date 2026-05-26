import json
from unittest.mock import MagicMock, patch


from slack_project.todo.sync import (
    apply_list_to_todo,
    build_entries_for_list,
    parse_list_entries_from_cache,
    run,
)


# ---------------------------------------------------------------------------
# parse_list_entries_from_cache
# ---------------------------------------------------------------------------


def test_parse_cache_normal(tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text(
        json.dumps({"entries": [{"title": "タスクA", "checked": False, "id": "e1"}]}),
        encoding="utf-8",
    )
    result = parse_list_entries_from_cache(cache)
    assert result == [("タスクA", False, "e1")]


def test_parse_cache_file_not_found(tmp_path):
    result = parse_list_entries_from_cache(tmp_path / "no_such_file.json")
    assert result == []


def test_parse_cache_invalid_json(tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text("not json", encoding="utf-8")
    result = parse_list_entries_from_cache(cache)
    assert result == []


def test_parse_cache_multiple_entries(tmp_path):
    cache = tmp_path / "cache.json"
    entries = [
        {"title": "A", "checked": False, "id": "1"},
        {"title": "B", "checked": True, "id": "2"},
    ]
    cache.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    result = parse_list_entries_from_cache(cache)
    assert len(result) == 2
    assert result[1] == ("B", True, "2")


# ---------------------------------------------------------------------------
# build_entries_for_list
# ---------------------------------------------------------------------------


def _make_task(norm, completed=False):
    return (f"- [ ] {norm}", completed, norm, None, None)


def test_build_entries_new_task():
    tasks = [_make_task("新タスク")]
    result = build_entries_for_list(tasks, [])
    assert len(result) == 1
    assert result[0][0] == "新タスク"
    assert result[0][2] is None  # entry_id is None (new)


def test_build_entries_existing_updated():
    tasks = [_make_task("タスクA", completed=True)]
    existing = [("タスクA", False, "e1")]
    result = build_entries_for_list(tasks, existing)
    assert len(result) == 1
    assert result[0][1] is True  # updated to completed
    assert result[0][2] == "e1"


def test_build_entries_completed_not_added():
    tasks = [_make_task("完了タスク", completed=True)]
    result = build_entries_for_list(tasks, [])
    assert result == []  # completed new tasks are not added


def test_build_entries_dedup():
    tasks = [_make_task("タスクA")]
    existing = [("タスクA", False, "e1")]
    result = build_entries_for_list(tasks, existing)
    assert len(result) == 1


# ---------------------------------------------------------------------------
# apply_list_to_todo
# ---------------------------------------------------------------------------


def _write_todo(path, content):
    path.write_text(content, encoding="utf-8")


def test_apply_list_marks_completed(tmp_path):
    todo = tmp_path / "todo.md"
    _write_todo(todo, "## 議事録由来タスク\n- [ ] タスクA\n")
    entries = [("タスクA", True, "e1")]
    apply_list_to_todo(todo, entries)
    assert "- [x] タスクA" in todo.read_text(encoding="utf-8")


def test_apply_list_no_entries(tmp_path):
    todo = tmp_path / "todo.md"
    original = "## 議事録由来タスク\n- [ ] タスクA\n"
    _write_todo(todo, original)
    apply_list_to_todo(todo, [])
    assert todo.read_text(encoding="utf-8") == original


def test_apply_list_no_matching_task(tmp_path):
    todo = tmp_path / "todo.md"
    original = "## 議事録由来タスク\n- [ ] タスクA\n"
    _write_todo(todo, original)
    entries = [("別のタスク", True, "e1")]
    apply_list_to_todo(todo, entries)
    assert "- [ ] タスクA" in todo.read_text(encoding="utf-8")


def test_apply_list_already_completed(tmp_path):
    todo = tmp_path / "todo.md"
    _write_todo(todo, "## 議事録由来タスク\n- [x] タスクA\n")
    entries = [("タスクA", True, "e1")]
    apply_list_to_todo(todo, entries)
    text = todo.read_text(encoding="utf-8")
    assert "- [x] タスクA" in text
    assert "- [ ] タスクA" not in text


# ---------------------------------------------------------------------------
# run — モードごとの動作確認（Slack API をモック）
# ---------------------------------------------------------------------------


def _make_project_dir(tmp_path, todo_content="## 議事録由来タスク\n- [ ] タスクA\n"):
    proj = tmp_path / "myproject"
    proj.mkdir()
    (proj / "todo.md").write_text(todo_content, encoding="utf-8")
    return proj


def _make_config(list_id="L001", token="xoxp-test"):
    return {"slack": {"list_id": list_id, "user_token": token}, "members": {}}


def test_run_project_dir_missing(tmp_path):
    success, msg = run(
        "nonexistent",
        project_root=tmp_path / "nonexistent",
    )
    assert success is False
    assert "存在しません" in msg


def test_run_todo_missing(tmp_path):
    proj = tmp_path / "myproject"
    proj.mkdir()
    success, msg = run("myproject", project_root=proj)
    assert success is False
    assert "todo.md" in msg


def test_run_check_only(tmp_path):
    proj = _make_project_dir(tmp_path)
    success, msg = run(
        "myproject",
        check_only=True,
        project_root=proj,
        load_config=lambda p: _make_config(list_id=None, token=None),
        get_token=lambda c: None,
        slack_lists=None,
    )
    assert success is True
    assert "チェック結果" in msg


def test_run_dry_run(tmp_path):
    proj = _make_project_dir(tmp_path)
    success, msg = run(
        "myproject",
        dry_run=True,
        project_root=proj,
        load_config=lambda p: _make_config(list_id=None, token=None),
        get_token=lambda c: None,
        slack_lists=None,
    )
    assert success is True
    assert "dry-run" in msg


def test_run_fetch_only_no_cache(tmp_path):
    proj = _make_project_dir(tmp_path)
    success, msg = run(
        "myproject",
        fetch_only=True,
        project_root=proj,
        load_config=lambda p: _make_config(list_id=None, token=None),
        get_token=lambda c: None,
        slack_lists=None,
    )
    assert success is True


def test_run_normal_no_list_id(tmp_path):
    proj = _make_project_dir(tmp_path)
    success, msg = run(
        "myproject",
        project_root=proj,
        load_config=lambda p: _make_config(list_id=None, token=None),
        get_token=lambda c: None,
        slack_lists=None,
    )
    assert success is False
    assert "list_id" in msg


def test_run_normal_no_token(tmp_path):
    proj = _make_project_dir(tmp_path)
    success, msg = run(
        "myproject",
        project_root=proj,
        load_config=lambda p: _make_config(list_id="L001", token=None),
        get_token=lambda c: None,
        slack_lists=None,
    )
    assert success is False
    assert "token" in msg.lower() or "user_token" in msg.lower()


def test_run_with_slack_api_mock(tmp_path):
    proj = _make_project_dir(tmp_path)
    mock_sl = MagicMock()
    mock_sl.list_entries.return_value = [("タスクA", True, "e1")]
    mock_sl.get_column_ids.return_value = (None, None, None, None)
    mock_sl.add_entry.return_value = None

    mock_web_client = MagicMock()
    # WebClient is imported lazily inside run(), so patch slack_sdk module
    with patch.dict("sys.modules", {"slack_sdk": MagicMock(WebClient=MagicMock(return_value=mock_web_client))}):
        success, msg = run(
            "myproject",
            project_root=proj,
            load_config=lambda p: _make_config(),
            get_token=lambda c: "xoxp-test",
            slack_lists=mock_sl,
        )
    assert success is True
