import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync TODO items for a project")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--fetch-only", action="store_true", help="Only fetch, do not sync")
    parser.add_argument("--check-only", action="store_true", help="Only check status, do not sync")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (do not apply changes)")
    args = parser.parse_args(argv)

    try:
        from slack_project.todo.sync import run
        from slack_project.workspace import ProjectWorkspace

        repo_root = Path.cwd()
        workspace = ProjectWorkspace(
            projects_root=repo_root / "projects",
            queue_dir=repo_root / "jobs",
        )
        success, message = run(
            workspace,
            args.project,
            fetch_only=args.fetch_only,
            check_only=args.check_only,
            dry_run=args.dry_run,
        )
        if success:
            print(message)
            return 0
        print(f"Error: {message}", file=sys.stderr)
        return 1
    except (ImportError, NotImplementedError) as e:
        print(f"Not implemented: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
