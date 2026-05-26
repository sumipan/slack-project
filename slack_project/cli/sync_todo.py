import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync TODO items for a project")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--fetch-only", action="store_true", help="Only fetch, do not sync")
    parser.add_argument("--check-only", action="store_true", help="Only check status, do not sync")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (do not apply changes)")
    args = parser.parse_args(argv)

    try:
        from slack_project.todo.sync import run
        success, message = run(project=args.project, fetch_only=args.fetch_only, check_only=args.check_only, dry_run=args.dry_run)
        if success:
            print(message)
            return 0
        else:
            print(f"Error: {message}", file=sys.stderr)
            return 1
    except (ImportError, NotImplementedError) as e:
        print(f"Not implemented: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
