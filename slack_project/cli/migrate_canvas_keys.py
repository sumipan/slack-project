"""Migrate config canvas keys from legacy names to the new split-key design.

Renames:
  slack.canvas_id          → slack.briefing_canvas_id
  project.slack_canvas_id  → project.slack_briefing_canvas_id

Files searched per project directory:
  config.yaml, config_local.yml, config.local.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap
except ImportError:
    print("Error: ruamel.yaml が必要です。pip install ruamel.yaml でインストールしてください。", file=sys.stderr)
    sys.exit(1)

_CONFIG_GLOBS = ("config.yaml", "config_local.yml", "config.local.yaml")

_YAML = YAML()
_YAML.preserve_quotes = True


def _rename_key(mapping: CommentedMap, old_key: str, new_key: str) -> bool:
    if old_key not in mapping:
        return False
    keys = list(mapping.keys())
    idx = keys.index(old_key)
    value = mapping[old_key]
    ca = mapping.ca.items.get(old_key)

    del mapping[old_key]
    mapping.insert(idx, new_key, value)
    if ca is not None:
        mapping.ca.items[new_key] = ca

    return True


def _migrate_config(content: str) -> tuple[str | None, str]:
    """Apply key renames. Returns (new_content, reason) or (None, reason) if skipped."""
    import io

    data = _YAML.load(content)
    if not isinstance(data, CommentedMap):
        return None, "YAML root is not a mapping"

    slack = data.get("slack")
    project = data.get("project")

    if isinstance(slack, CommentedMap) and "briefing_canvas_id" in slack:
        return None, "slack.briefing_canvas_id が既に存在します。手動マージが必要です。"

    changed = False

    if isinstance(slack, CommentedMap):
        changed |= _rename_key(slack, "canvas_id", "briefing_canvas_id")

    if isinstance(project, CommentedMap):
        changed |= _rename_key(project, "slack_canvas_id", "slack_briefing_canvas_id")

    if not changed:
        return content, "変更なし"

    buf = io.StringIO()
    _YAML.dump(data, buf)
    return buf.getvalue(), "renamed"


def _diff_lines(old: str, new: str, path: Path) -> str:
    import difflib

    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        )
    )


def migrate_projects(projects_dir: Path, *, dry_run: bool) -> int:
    """Walk projects_dir/*/config files and apply canvas key renames.

    Returns the number of files actually modified (or that would be modified in dry_run).
    """
    if not projects_dir.is_dir():
        print(f"Error: ディレクトリが存在しません: {projects_dir}", file=sys.stderr)
        return -1

    modified = 0

    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        for glob in _CONFIG_GLOBS:
            cfg = project_dir / glob
            if not cfg.exists():
                continue

            original = cfg.read_text(encoding="utf-8")
            new_content, reason = _migrate_config(original)

            if new_content is None:
                print(f"[スキップ] {cfg}: {reason}")
                continue

            if new_content == original:
                continue

            modified += 1

            if dry_run:
                diff = _diff_lines(original, new_content, cfg)
                if diff:
                    print(diff, end="")
            else:
                cfg.write_text(new_content, encoding="utf-8")
                print(f"[更新] {cfg}")

    return modified


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="プロジェクト config の Canvas キーを新命名規則にリネームします"
    )
    parser.add_argument(
        "--projects-dir",
        required=True,
        metavar="DIR",
        help="プロジェクトディレクトリの親ディレクトリ（projects/ など）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="変更予定の diff を stdout に出力するのみ（実ファイルは変更しない）",
    )
    args = parser.parse_args(argv)

    projects_dir = Path(args.projects_dir)
    result = migrate_projects(projects_dir, dry_run=args.dry_run)
    if result == -1:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
