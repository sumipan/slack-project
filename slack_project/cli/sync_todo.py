import argparse
import sys
from pathlib import Path

from slack_project.config_loader import get_slack_token, load_project_config
from slack_project.slack.client import SlackClient
from slack_project.todo.canvas import build_canvas_markdown
from slack_project.workspace import ProjectWorkspace


def _get_canvas_id(config: dict) -> str | None:
    slack = config.get("slack") or {}
    return slack.get("todo_canvas_id")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Push project todo.md to Slack Canvas")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (do not call Slack API)")
    args = parser.parse_args(argv)

    try:
        repo_root = Path.cwd()
        workspace = ProjectWorkspace(
            projects_root=repo_root / "projects",
            queue_dir=repo_root / "jobs",
        )
        project_dir = workspace.project_dir(args.project)
        if not project_dir.is_dir():
            print(f"Error: プロジェクトフォルダが存在しません: {project_dir}", file=sys.stderr)
            return 1

        todo_path = workspace.todo_path(args.project)
        if not todo_path.exists():
            print(f"Error: todo.md が存在しません: {todo_path}", file=sys.stderr)
            return 1

        config = load_project_config(project_dir)
        token = get_slack_token(config)
        canvas_id = _get_canvas_id(config)
        if not token:
            print("Error: Slack トークンが設定されていません", file=sys.stderr)
            return 1
        if not canvas_id:
            print("Error: slack.todo_canvas_id が未設定です。config.yaml に追加してください。", file=sys.stderr)
            return 1

        raw_text = todo_path.read_text(encoding="utf-8")
        markdown = build_canvas_markdown(raw_text)
        client = SlackClient(token, dry_run=args.dry_run)
        client.update_canvas(canvas_id=canvas_id, markdown=markdown)
        if args.dry_run:
            print(f"Canvas dry-run push completed: {args.project}")
        else:
            print(f"Canvas push completed: {args.project}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
