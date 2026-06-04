# slack-project

Markdown ファイルベースのプロジェクト管理フロー向け Slack 連携パッケージ。会議録の Slack 投稿・Todo の Canvas 同期・週次 Slack ログ収集を 3 つの CLI と Python API で提供する。汎用 Slack Bot SDK（Bolt 等）の置き換えではなく、`projects/<name>/` ディレクトリ構成を前提とした日本語ワークフローに特化したツールです。

[![version](https://img.shields.io/badge/version-0.2.1-blue)](https://github.com/sumipan/slack-project/releases)
[![stability](https://img.shields.io/badge/stability-pre--1.0-orange)](https://github.com/sumipan/slack-project)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://pypi.org/project/slack-project/)

## Installation

```bash
pip install slack-project
```

前提条件: Python 3.11 以上、`ghdag >= 0.25.0`（依存として自動インストール）

開発用:

```bash
pip install -e ".[dev]"
```

## Quick Start

プロジェクトディレクトリを用意する:

```
projects/
  myproject/
    config.yaml   ← Slack トークン・ID を記載
    todo.md       ← タスク一覧
```

```yaml
# projects/myproject/config.yaml
slack:
  user_token: "xoxp-..."
  canvas_id: "F0123CANVAS"
  channel_id: "C0123CHANNEL"
```

**Todo を Canvas に同期する:**

```bash
slack-project-sync-todo --project myproject
```

**会議録を Slack に投稿する:**

```bash
slack-project-post-docs --minutes projects/myproject/議事録/2026-06-01.md
```

**Slack ログを取得する:**

```bash
slack-project-fetch-logs --project myproject --from-date 2026-05-01
```

**Python API 使用例:**

```python
from slack_project.slack.client import SlackClient
from slack_project.todo import build_canvas_markdown

client = SlackClient(token="xoxp-...", dry_run=False)
todo_text = open("projects/myproject/todo.md").read()
markdown = build_canvas_markdown(todo_text)
client.update_canvas(canvas_id="F0123CANVAS", markdown=markdown)
```

## CLI Reference

| コマンド | 説明 |
|---------|------|
| `slack-project-sync-todo` | `todo.md` を Slack Canvas に一方向同期 |
| `slack-project-post-docs` | 会議録 Markdown を Slack チャンネルに投稿 |
| `slack-project-fetch-logs` | Slack チャンネル履歴を週単位で取得 |

### slack-project-sync-todo

```
slack-project-sync-todo --project <name> [--dry-run]
```

| 引数 | 必須 | 説明 |
|------|------|------|
| `--project` | ✅ | プロジェクト名（`projects/<name>/` のディレクトリ名） |
| `--dry-run` | | Slack API を呼ばずプレビューのみ |

### slack-project-post-docs

```
slack-project-post-docs --minutes <PATH> [--dry-run]
```

| 引数 | 必須 | 説明 |
|------|------|------|
| `--minutes` | ✅ | 会議録 Markdown ファイルのパス |
| `--dry-run` | | Slack API を呼ばずプレビューのみ |

### slack-project-fetch-logs

```
slack-project-fetch-logs --project <name> [--from-date YYYY-MM-DD] [--safe-ratelimit]
```

| 引数 | 必須 | 説明 |
|------|------|------|
| `--project` | ✅ | プロジェクト名 |
| `--from-date` | | 取得開始日（YYYY-MM-DD、デフォルト: `2020-01-01`） |
| `--safe-ratelimit` | | API 呼び出し間隔を広げてレート制限を回避 |

## Public API

### `slack_project.slack`

| シンボル | 種別 | 説明 |
|---------|------|------|
| `SlackClient(token, dry_run)` | クラス | Slack REST API ラッパー（POST / GET / Canvas 編集・ページネーション対応） |
| `fetch_weekly_logs(project, from_date, safe_ratelimit)` | 関数 | 週単位のチャンネル履歴取得 |
| `get_week_ranges(from_date)` | 関数 | 週区切り（土曜〜金曜）の日付リスト生成 |

### `slack_project.docs`

| シンボル | 種別 | 説明 |
|---------|------|------|
| `ParsedMinutes` | dataclass | 会議録の解析結果（title, participants, overview, body_text, tasks） |
| `Task` | dataclass | アクションアイテム（summary, assignees, due_date, description, raw_line） |
| `TodoItem` | dataclass | Todo アイテム（assignee, content, due） |
| `parse_minutes(text)` | 関数 | Markdown 会議録を構造化パース |
| `format_head_blocks(parsed)` | 関数 | Block Kit ヘッダーブロック生成 |
| `format_body_blocks(parsed)` | 関数 | Block Kit 本文ブロック生成 |
| `format_action_blocks(parsed)` | 関数 | Block Kit アクションアイテムブロック生成 |
| `fallback_text(parsed)` | 関数 | Slack 通知用フォールバックテキスト生成 |
| `extract_tasks(parsed)` | 関数 | 会議録から `TodoItem` リストを抽出 |
| `build_todo_section(meeting_date, meeting_name, tasks, source_label)` | 関数 | `todo.md` 追記用 Markdown セクション生成 |

### `slack_project.todo`

| シンボル | 種別 | 説明 |
|---------|------|------|
| `parse_todo_tasks(text)` | 関数 | `todo.md` のタスクリストをパース |
| `get_completed_sections(tasks)` | 関数 | 全タスクが完了したセクションを抽出 |
| `build_canvas_markdown(text)` | 関数 | 未完了タスクのみの Canvas 同期用 Markdown 生成 |
| `push_to_canvas(canvas_id, markdown, client)` | 関数 | Canvas へプッシュ |

### `slack_project.briefing`

| シンボル | 種別 | 説明 |
|---------|------|------|
| `fetch_slack_log(project, from_date)` | 関数 | プロジェクトのチャンネル履歴を取得 |
| `run_auto_update(projects_root)` | 関数 | 全プロジェクトのログを一括取得 |
| `post_summary(project, text, client)` | 関数 | チャンネルにサマリーを投稿 |
| `update_canvas(project, text, client)` | 関数 | ブリーフィング Canvas を更新 |
| `get_briefing_path(workspace, project)` | 関数 | `briefing.md` のパスを解決 |

### `slack_project.collector`

| シンボル | 種別 | 説明 |
|---------|------|------|
| `ProjectContext` | dataclass | 収集済みプロジェクトデータ（name, minutes, todos, slack_log） |
| `collect_context(workspace, days)` | 関数 | 直近 N 日の会議録・Todo・Slack ログを集約 |

### `slack_project.workspace`

| シンボル | 種別 | 説明 |
|---------|------|------|
| `ProjectWorkspace(projects_root, queue_dir)` | dataclass | プロジェクトパス管理（`project_dir()` / `briefing_path()` / `todo_path()` / `minutes_dir()` / `config_paths()`） |
| `normalize_project_name(project)` | 関数 | `projects/foo` → `foo` に正規化 |

### `slack_project.config` / `slack_project.config_loader`

| シンボル | 種別 | 説明 |
|---------|------|------|
| `ProjectConfig(project_name, base_dir)` | dataclass | プロジェクトパス設定（`.project_dir` プロパティ / `.validate()` メソッド） |
| `load_project_config(project_root)` | 関数 | YAML 設定ファイルを deep-merge でロード |
| `get_slack_token(config)` | 関数 | 設定 dict から Slack トークンを抽出 |

### `slack_project.transcript`

| シンボル | 種別 | 説明 |
|---------|------|------|
| `parse_source_path(path)` | 関数 | リソースパスからメタデータを抽出 |
| `detect_transcript_type(text)` | 関数 | Teams / Zoom 文字起こし形式を判別 |

### `slack_project.ghdag_bridge`

| シンボル | 種別 | 説明 |
|---------|------|------|
| `submit_order(order_content, *, model, ...)` | 関数 | ghdag パイプラインにジョブをキュー投入 |

## Architecture

```
slack_project/
├── slack/
│   ├── client.py       SlackClient — REST API ラッパー（投稿・取得・Canvas 編集・ページネーション）
│   └── fetch.py        週単位のチャンネル履歴取得（get_week_ranges / fetch_weekly_logs）
├── docs/
│   ├── parser.py       会議録 Markdown パーサー（ParsedMinutes / Task）
│   ├── formatter.py    Block Kit JSON フォーマッター（format_*_blocks / fallback_text）
│   └── to_todo.py      会議録 → Todo 変換（TodoItem / extract_tasks / build_todo_section）
├── todo/
│   ├── parser.py       todo.md パーサー（担当者・期日・完了フラグ抽出）
│   └── canvas.py       Slack Canvas への一方向同期（build_canvas_markdown / push_to_canvas）
├── briefing/
│   ├── weekly.py       週次ブリーフィング・Slack ログ取得（fetch_slack_log / run_auto_update / post_summary）
│   └── updater.py      ブリーフィング Canvas 更新（update_canvas / get_briefing_path）
├── collector.py        直近 N 日の会議録・Todo・Slack ログ集約（ProjectContext / collect_context）
├── workspace.py        プロジェクトパス管理（ProjectWorkspace / normalize_project_name）
├── config.py           プロジェクト設定データクラス（ProjectConfig）
├── config_loader.py    YAML 設定 deep-merge ロード（load_project_config / get_slack_token）
├── transcript.py       文字起こし形式判別（Teams / Zoom）
├── ghdag_bridge.py     ghdag パイプライン連携（submit_order）
└── cli/
    ├── fetch_logs.py   slack-project-fetch-logs エントリポイント
    ├── post_docs.py    slack-project-post-docs エントリポイント
    └── sync_todo.py    slack-project-sync-todo エントリポイント
```

## Configuration

`projects/<project>/` 配下の以下のファイルを検索し、見つかったものを順に deep-merge する。

| ファイル | 用途 |
|---------|------|
| `config.yaml` | プロジェクト共通設定 |
| `config_local.yml` | ローカル上書き設定（`.gitignore` 推奨） |
| `config.local.yaml` | ローカル上書き設定（`.gitignore` 推奨） |

**設定キー一覧**

| キー | 型 | 説明 |
|------|----|------|
| `slack.user_token` | str | Slack ユーザートークン（Canvas API に必須） |
| `slack.token` | str | `user_token` の代替キー |
| `slack.channel_id` | str | 投稿先 Slack チャンネル ID |
| `slack.canvas_id` | str | Todo 同期先 Canvas ID |
| `slack.todo_canvas_id` | str | 完了タスク用 Canvas ID |
| `project.slack_channel_id` | str | `slack.channel_id` の代替キー |
| `project.slack_canvas_id` | str | `slack.canvas_id` の代替キー |
| `weekly_summary.enabled` | bool | 週次サマリー生成の有効化 |
| `advisor_enabled` | bool | コンテキスト収集（briefing）の有効化 |
| `slack_token` | str | トップレベルトークン（レガシー互換） |
| `slack_channel_id` | str | トップレベルチャンネル ID（レガシー互換） |

環境変数は使用しない。設定はすべて YAML ファイル経由で行う。

## Error Reference

slack-project 専用の例外クラスは定義しない。標準例外を使用する。

| 例外 | 発生箇所 | 条件 |
|------|---------|------|
| `FileNotFoundError` | `ProjectConfig.validate()` / `cli/sync_todo.py` | プロジェクトディレクトリまたは `todo.md` が存在しない |
| `ValueError` | `workspace.py` / `transcript.py` | 不正なパス形式・日付パース失敗 |
| `ImportError` | `config_loader.py` / `cli/*.py` | `PyYAML` / `requests` / `ghdag` が未インストール |
| `RuntimeError` | `slack/client.py` | Slack API エラーレスポンス |

## Not（これは何でないか）

- **Slack Bot SDK ではない**: リアルタイムイベント受信・ボット応答には [Bolt for Python](https://github.com/slackapi/bolt-python) を使う
- **汎用タスク管理ツールではない**: `projects/<name>/todo.md` 構成を前提としており、任意の形式には対応しない
- **Slack ワークスペース管理ツールではない**: チャンネル作成・ユーザー管理・権限変更には対応しない
- **nexus 専用内部ツールではない**: nexus の `tools/project/` から分離した独立 OSS として利用できる

## Public API Stability

**pre-1.0（`0.Y.Z` フェーズ）。マイナーバージョン（Y）の変化で破壊的変更が発生しうる。**

| バージョン変化 | 互換性 |
|--------------|-------|
| `0.Y.Z` → `0.Y.(Z+1)` | 後方互換パッチ |
| `0.Y.Z` → `0.(Y+1).0` | 破壊的変更あり（CHANGELOG を確認） |

`1.0.0` 到達まで API の安定性は保証しない。

## License

[MIT License](./LICENSE) — Copyright 2026 ngystks

SPDX-License-Identifier: `MIT`
