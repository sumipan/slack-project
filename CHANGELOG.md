# Changelog

## [0.3.0] - 2026-09-26

- feat(briefing): `fetch_slack_log(..., jsonl_dir=None)` appends parent messages and replies to `jsonl_dir/YYYY-MM-DD.jsonl` (JST date) with `id` / `ts` / `author` / `text` / `thread_ts` / `raw`, skipping ids already present. Default output is unchanged
- feat(todo): add `parser.MINUTES_SECTION` and `parse_todo_tasks_all`, which returns tasks from every `##` section with the section title as a 7th element. `parse_todo_tasks` still returns 6 elements
- feat(todo): `build_canvas_markdown` groups tasks by `##` then `###` section; a minutes-only todo.md renders exactly as before
- feat(todo): Canvas `[x]` import now applies to every `##` section (check-on-only as before)

## [0.1.4] - 2026-05-29

- ci: add `.github/workflows/test.yml` (pytest, ruff, mypy on push/PR)
- fix(todo): defer `slack_lists` and config loader resolution until after path validation
- chore: align `__version__` with `pyproject.toml`; add historical CHANGELOG entries
- build: pin `ghdag>=0.25.0`; add `ruff` and `mypy` to dev dependencies

## [0.1.3] - 2026-05-26

- feat(todo): slack_project.todo サブパッケージ追加（parser + sync）
- feat(cli): CLI エントリポイント追加（fetch_logs, post_docs, sync_todo）
- feat(briefing,transcript,ghdag-bridge): コアモジュール移植

## [0.1.2] - 2026-05-26

- feat(docs): slack_project.docs サブパッケージ追加（parser, formatter, to_todo）

## [0.1.1] - 2026-05-26

- feat(slack): SlackClient, Lists, fetch モジュール移植
- feat(skeleton): パッケージスケルトン作成
