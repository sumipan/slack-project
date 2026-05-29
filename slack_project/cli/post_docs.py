import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Post minutes document to Slack")
    parser.add_argument("--minutes", required=True, type=Path, metavar="PATH", help="Path to minutes file")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (do not post)")
    args = parser.parse_args(argv)

    try:
        from slack_project.docs.formatter import run  # type: ignore[attr-defined]
        result = run(minutes=args.minutes, dry_run=args.dry_run)
        print(result)
        return 0
    except (ImportError, NotImplementedError) as e:
        print(f"Not implemented: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
