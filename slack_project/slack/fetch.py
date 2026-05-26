"""slack_project.slack.fetch — 週次 Slack ログ取得モジュール"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Tokyo")


def get_week_ranges(from_date: datetime, to_date: datetime) -> list[tuple[datetime, datetime]]:
    """
    from_date〜to_date を土曜始まり・金曜終わりの週に分割する。

    Returns:
        [(土曜 00:00:00, 金曜 23:59:59), ...] のリスト
    """
    if from_date > to_date:
        return []

    def saturday_of(d: datetime) -> datetime:
        days = (d.weekday() + 2) % 7
        return d.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)

    ranges: list[tuple[datetime, datetime]] = []
    current = saturday_of(from_date)

    while current <= to_date:
        fri = current + timedelta(days=6)
        fri = fri.replace(hour=23, minute=59, second=59, microsecond=999999)
        ranges.append((current, fri))
        current += timedelta(days=7)

    return ranges


def fetch_weekly_logs(
    client,
    channel_id: str,
    from_date: datetime,
    to_date: datetime,
    output_dir: Path,
    *,
    safe_ratelimit: bool = False,
) -> dict[str, int]:
    """
    指定期間の週次 Slack ログを取得し、output_dir に保存する。

    Args:
        client: SlackClient インスタンス（conversations_history メソッドを持つ）
        channel_id: Slack チャンネル ID
        from_date: 取得開始日（tzinfo 付き）
        to_date: 取得終了日（tzinfo 付き）
        output_dir: ログファイルの出力先ディレクトリ
        safe_ratelimit: True の場合 API 呼び出し間に sleep を挿入

    Returns:
        {"ok": int, "skip": int, "fail": int}
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    week_ranges = get_week_ranges(from_date, to_date)
    ok = 0
    skip = 0
    fail = 0

    for sat, fri in week_ranges:
        out_name = f"{sat.strftime('%Y%m%d')}_{fri.strftime('%Y%m%d')}_Slackのログ.md"
        out_path = output_dir / out_name
        if out_path.exists():
            skip += 1
            continue

        try:
            oldest = str(sat.timestamp())
            latest = str(fri.timestamp())
            messages = []
            cursor = None

            while True:
                kwargs: dict = {
                    "channel": channel_id,
                    "oldest": oldest,
                    "latest": latest,
                    "limit": 200,
                }
                if cursor:
                    kwargs["latest"] = cursor
                resp = client.conversations_history(**kwargs)
                msgs = resp.get("messages") or []
                messages.extend(msgs)
                if not resp.get("has_more"):
                    break
                meta = resp.get("response_metadata") or {}
                cursor = meta.get("next_cursor") or ""
                if not cursor:
                    break
                if safe_ratelimit:
                    time.sleep(1)

            lines = [f"# Slack ログ {sat.strftime('%Y-%m-%d')} 〜 {fri.strftime('%Y-%m-%d')}\n"]
            for msg in reversed(messages):
                ts = msg.get("ts", "")
                user = msg.get("user", "unknown")
                text = msg.get("text", "")
                lines.append(f"- [{ts}] {user}: {text}\n")

            out_path.write_text("".join(lines), encoding="utf-8")
            ok += 1

            if safe_ratelimit and (sat, fri) != week_ranges[-1]:
                time.sleep(1)

        except Exception:
            fail += 1

    return {"ok": ok, "skip": skip, "fail": fail}
