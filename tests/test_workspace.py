from pathlib import Path

from slack_project.workspace import ProjectWorkspace, normalize_project_name


class TestNormalizeProjectName:
    def test_plain_name(self):
        assert normalize_project_name("my-project") == "my-project"

    def test_projects_prefix(self):
        assert normalize_project_name("projects/my-project") == "my-project"


class TestProjectWorkspace:
    def test_briefing_path(self):
        ws = ProjectWorkspace(Path("/tmp/p"), Path("/tmp/q"))
        assert ws.briefing_path("proj") == Path("/tmp/p/proj/briefing.md")

    def test_project_dir(self):
        ws = ProjectWorkspace(Path("/tmp/p"), Path("/tmp/q"))
        assert ws.project_dir("projects/foo") == Path("/tmp/p/foo")

    def test_config_paths(self):
        ws = ProjectWorkspace(Path("/tmp/p"), Path("/tmp/q"))
        paths = ws.config_paths("x")
        assert paths[0] == Path("/tmp/p/x/config.yaml")
        assert len(paths) == 3

    def test_minutes_and_todo_paths(self):
        ws = ProjectWorkspace(Path("/tmp/p"), Path("/tmp/q"))
        assert ws.minutes_dir("x") == Path("/tmp/p/x/議事録")
        assert ws.todo_path("x") == Path("/tmp/p/x/todo.md")


class TestNoHardcodedProjectsPath:
    def test_no_path_projects_literal_in_slack_project(self):
        import subprocess

        root = Path(__file__).resolve().parent.parent / "slack_project"
        result = subprocess.run(
            ["grep", "-r", 'Path("projects")', str(root)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, result.stdout

    def test_no_repo_root_in_slack_project(self):
        import subprocess

        root = Path(__file__).resolve().parent.parent / "slack_project"
        result = subprocess.run(
            ["grep", "-r", "REPO_ROOT", str(root)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, result.stdout

    def test_no_repo_root_in_ghdag_bridge(self):
        import subprocess

        path = Path(__file__).resolve().parent.parent / "slack_project" / "ghdag_bridge.py"
        result = subprocess.run(
            ["grep", "_REPO_ROOT", str(path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, result.stdout

    def test_no_tools_project_import(self):
        import subprocess

        root = Path(__file__).resolve().parent.parent / "slack_project"
        for pattern in ("from tools.project", "import tools.project"):
            result = subprocess.run(
                ["grep", "-r", pattern, str(root)],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 1, f"{pattern}: {result.stdout}"
