"""
slack_project.collector — プロジェクトコンテキスト収集

projects_root 配下の advisor_enabled: true なプロジェクトから
直近 N 日の議事録・未完了 todo・Slack ログを収集する。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from slack_project.workspace import ProjectWorkspace

try:
    import yaml
except ImportError as exc:
    raise ImportError("PyYAML が必要です: pip install pyyaml") from exc

_EXCERPT_CHARS = 500
_SLACK_LOG_MAX_CHARS = 2000


@dataclass
class ProjectContext:
    name: str
    minutes: list[dict[str, str]] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)
    slack_log: str = ""


def collect_context(
    workspace: ProjectWorkspace,
    *,
    days: int = 7,
    project_filter: str | None = None,
) -> dict[str, ProjectContext]:
    projects_dir = workspace.projects_root
    if not projects_dir.is_dir():
        return {}

    cutoff = datetime.now() - timedelta(days=days)
    result: dict[str, ProjectContext] = {}

    for entry in sorted(projects_dir.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name

        if name == "project.exsample":
            continue
        if project_filter and name != project_filter:
            continue

        config_path = entry / "config.yaml"
        if not config_path.exists():
            continue

        config = _load_yaml(config_path)
        if not config.get("advisor_enabled", False):
            continue

        ctx = ProjectContext(name=name)
        ctx.minutes = _collect_minutes(entry, cutoff)
        ctx.todos = _collect_todos(entry)
        ctx.slack_log = _collect_slack_log(entry, cutoff)
        result[name] = ctx

    return result


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _collect_minutes(project_dir: Path, cutoff: datetime) -> list[dict[str, str]]:
    minutes_dir = project_dir / "議事録"
    if not minutes_dir.is_dir():
        return []

    items = []
    for f in sorted(minutes_dir.glob("*.md")):
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if mtime < cutoff:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            text = ""
        items.append({"name": f.name, "excerpt": text[:_EXCERPT_CHARS]})

    return items


def _collect_todos(project_dir: Path) -> list[str]:
    todo_path = project_dir / "todo.md"
    if not todo_path.exists():
        return []

    todos = []
    try:
        lines = todo_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- [ ]"):
            todos.append(stripped)

    return todos


def _collect_slack_log(project_dir: Path, cutoff: datetime) -> str:
    assets_dir = project_dir / "assets"
    if not assets_dir.is_dir():
        return ""

    collected = []
    for f in sorted(assets_dir.glob("*_Slackのログ.md"), reverse=True):
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if mtime < cutoff:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        collected.append(text)

    combined = "\n\n".join(collected)
    return combined[:_SLACK_LOG_MAX_CHARS]


__all__ = ["ProjectContext", "collect_context"]
