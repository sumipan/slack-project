from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def normalize_project_name(project: str) -> str:
    """プロジェクト名を正規化する（projects/ プレフィクス除去）。"""
    project_arg = (project or "").strip().replace("\\", "/")
    if project_arg.startswith("projects/"):
        parts = project_arg.split("/")
        return parts[1] if len(parts) > 1 else parts[0]
    return project_arg.rstrip("/")


@dataclass(frozen=True)
class ProjectWorkspace:
    projects_root: Path
    queue_dir: Path

    def project_dir(self, project: str) -> Path:
        return self.projects_root / normalize_project_name(project)

    def briefing_path(self, project: str) -> Path:
        return self.project_dir(project) / "briefing.md"

    def config_paths(self, project: str) -> list[Path]:
        base = self.project_dir(project)
        return [base / name for name in ("config.yaml", "config_local.yml", "config.local.yaml")]

    def minutes_dir(self, project: str) -> Path:
        return self.project_dir(project) / "議事録"

    def todo_path(self, project: str) -> Path:
        return self.project_dir(project) / "todo.md"


__all__ = ["ProjectWorkspace", "normalize_project_name"]
