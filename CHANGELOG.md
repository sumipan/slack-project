# Changelog

## [Unreleased]

### BREAKING CHANGES

- **`slack.canvas_id` キーを廃止し、用途別キーに分離** ([#2272](https://github.com/sumipan/nexus/issues/2272))
  - `slack.briefing_canvas_id` — ブリーフィング Canvas（briefing.md → Canvas 一方向）
  - `slack.todo_canvas_id` — TODO Canvas（todo.md ↔ Canvas 双方向）
  - `project.slack_canvas_id` fallback も完全削除
  - マイグレーション: `python3 -m slack_project.cli.migrate_canvas_keys --projects-dir <dir>` を実行すること
- **`briefing/updater.py`**: 未設定時エラーメッセージが `slack.briefing_canvas_id` キー名を案内するよう変更
- **`cli/sync_todo.py`**: 未設定時エラーメッセージが `slack.todo_canvas_id` キー名を案内するよう変更

### Added

- `slack_project.cli.migrate_canvas_keys` — プロジェクト config の Canvas キーリネーム CLI (`--projects-dir`, `--dry-run`)

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
