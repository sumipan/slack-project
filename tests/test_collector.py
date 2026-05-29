from pathlib import Path

from slack_project.collector import collect_context
from slack_project.workspace import ProjectWorkspace


def _workspace(tmp_path: Path) -> ProjectWorkspace:
    return ProjectWorkspace(
        projects_root=tmp_path / "projects",
        queue_dir=tmp_path / "jobs",
    )


def test_collect_context_empty(tmp_path):
    ws = _workspace(tmp_path)
    ws.projects_root.mkdir(parents=True)
    assert collect_context(ws, days=7) == {}


def test_collect_context_advisor_enabled(tmp_path):
    ws = _workspace(tmp_path)
    proj = ws.projects_root / "proj-a"
    proj.mkdir(parents=True)
    (proj / "config.yaml").write_text("advisor_enabled: true\n", encoding="utf-8")
    (proj / "todo.md").write_text("- [ ] タスク1\n", encoding="utf-8")

    result = collect_context(ws, days=7)
    assert "proj-a" in result
    assert result["proj-a"].todos == ["- [ ] タスク1"]
