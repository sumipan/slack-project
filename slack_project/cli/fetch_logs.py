import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch Slack logs for a project")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--from-date", default="2020-01-01", metavar="YYYY-MM-DD", help="Start date (default: 2020-01-01)")
    parser.add_argument("--safe-ratelimit", action="store_true", help="Enable safe rate limiting")
    args = parser.parse_args(argv)

    try:
        from slack_project.slack.fetch import fetch_weekly_logs
        count = fetch_weekly_logs(project=args.project, from_date=args.from_date, safe_ratelimit=args.safe_ratelimit)
        print(f"Fetched {count} logs")
        return 0
    except (ImportError, NotImplementedError) as e:
        print(f"Not implemented: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
