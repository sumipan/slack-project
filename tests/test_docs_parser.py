from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from slack_project.docs.parser import parse_minutes, ParsedMinutes

SAMPLE_MARKDOWN = """\
# 2026-03-01 定例

## ミーティング

* 日時：2026-03-01 14:00
* 参加者：太郎, 花子

## 概要

今回の定例では、リリース計画と課題対応について話し合いました。

## 取り上げられたトピック

* リリース計画
* バグ対応

## 3. アクションアイテム

```
- [ ] 太郎：レビュー 2026-03-01
  - PRのレビューをすること
- [ ] 花子・次郎：デプロイ確認
```
"""

ORIGINAL_PARSER = Path("/Users/ngystks/Github/diary/tools/project/minutes_parser.py")


def test_empty_string():
    parsed = parse_minutes("")
    assert parsed == ParsedMinutes(title="", participants="", overview="", body_text="", tasks=[])


def test_title():
    parsed = parse_minutes("# タイトル\n")
    assert parsed.title == "タイトル"


def test_participants():
    parsed = parse_minutes("* 参加者：A, B\n")
    assert parsed.participants == "A, B"


def test_overview():
    md = "## 概要\n概要テキストです。\n\n## 次のセクション\n"
    parsed = parse_minutes(md)
    assert parsed.overview == "概要テキストです。"


def test_overview_truncated_to_500():
    long_text = "あ" * 600
    md = f"## 概要\n{long_text}\n\n## 次のセクション\n"
    parsed = parse_minutes(md)
    assert len(parsed.overview) <= 500


def test_task_from_action_items():
    parsed = parse_minutes(SAMPLE_MARKDOWN)
    assert len(parsed.tasks) >= 1
    task = parsed.tasks[0]
    assert task.assignees == ["太郎"]
    assert task.due_date == "2026-03-01"
    assert "レビュー" in task.summary


def test_task_description():
    parsed = parse_minutes(SAMPLE_MARKDOWN)
    assert parsed.tasks[0].description == "PRのレビューをすること"


def test_task_multiple_assignees():
    parsed = parse_minutes(SAMPLE_MARKDOWN)
    assert len(parsed.tasks) >= 2
    task = parsed.tasks[1]
    assert "花子" in task.assignees
    assert "次郎" in task.assignees


def test_task_alt_section():
    md = """\
# 会議

## アクション・タスク

```
- [ ] 太郎：確認作業
```
"""
    parsed = parse_minutes(md)
    assert len(parsed.tasks) == 1
    assert parsed.tasks[0].assignees == ["太郎"]


def test_custom_section_overview():
    md = "## Summary\n概要テキストです。\n\n## Next\n"
    parsed = parse_minutes(md, section_overview="Summary")
    assert parsed.overview == "概要テキストです。"


@pytest.mark.skipif(not ORIGINAL_PARSER.exists(), reason="Original parser not available")
def test_default_args_same_as_original(tmp_path):
    import sys
    mod_name = "minutes_parser_orig"
    spec = importlib.util.spec_from_file_location(mod_name, ORIGINAL_PARSER)
    orig_mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = orig_mod
    spec.loader.exec_module(orig_mod)

    md_file = tmp_path / "test.md"
    md_file.write_text(SAMPLE_MARKDOWN, encoding="utf-8")

    orig = orig_mod.parse_minutes(md_file)
    new = parse_minutes(SAMPLE_MARKDOWN)

    assert new.title == orig.title
    assert new.participants == orig.participants
    assert new.overview == orig.overview
    assert new.body_text == orig.body_text
    assert len(new.tasks) == len(orig.tasks)
    for t_new, t_orig in zip(new.tasks, orig.tasks):
        assert t_new.summary == t_orig.summary
        assert t_new.assignees == t_orig.assignees
        assert t_new.due_date == t_orig.due_date
