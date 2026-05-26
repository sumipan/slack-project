from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

_JST = ZoneInfo("Asia/Tokyo")
_SLACK_API_BASE = "https://slack.com/api/"


def _load_project_config(project: str) -> dict[str, Any]:
    try:
        import yaml
    except ImportError:
        return {}

    config: dict[str, Any] = {}
    for name in ("config.yaml", "config_local.yml", "config.local.yaml"):
        p = Path("projects") / project / name
        if p.exists():
            with open(p, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                config = _deep_merge(config, data)
    return config


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if value is None:
            continue
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _get_slack_token(config: dict[str, Any]) -> str | None:
    slack = config.get("slack") or {}
    return slack.get("user_token") or slack.get("token") or config.get("slack_token")


def _get_slack_channel_id(config: dict[str, Any]) -> str | None:
    slack = config.get("slack") or {}
    return (
        slack.get("channel_id")
        or config.get("slack_channel_id")
        or (config.get("project") or {}).get("slack_channel_id")
    )


def _discover_projects() -> list[dict]:
    try:
        import yaml
    except ImportError:
        return []

    projects_dir = Path("projects")
    if not projects_dir.is_dir():
        return []

    results = []
    for config_path in sorted(projects_dir.glob("*/config.yaml")):
        project_dir = config_path.parent
        name = project_dir.name
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        slack = config.get("slack") or {}
        channel_id = (slack.get("channel_id") or "").strip()
        if not channel_id:
            continue
        ws = config.get("weekly_summary") or {}
        if not ws.get("enabled", True):
            continue
        has_local = any(
            (project_dir / n).exists()
            for n in ("config_local.yml", "config.local.yaml")
        )
        if not has_local:
            continue
        results.append({"name": name, "channel_id": channel_id})
    return results


def _calc_period(
    week: str,
    since: str | None,
    until: str | None,
) -> tuple[datetime, datetime]:
    """期間の開始・終了 datetime（JST aware）を計算して返す。"""
    if since and until:
        period_start = datetime.strptime(since, "%Y-%m-%d").replace(
            hour=0, minute=0, second=0, tzinfo=_JST
        )
        period_end = datetime.strptime(until, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, tzinfo=_JST
        )
        return period_start, period_end

    now = datetime.now(_JST)
    days_since_sat = (now.weekday() - 5) % 7
    this_saturday = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=days_since_sat
    )

    if week == "current":
        period_start = this_saturday
        period_end = (this_saturday + timedelta(days=6)).replace(hour=23, minute=59, second=59)
    else:  # "last"
        last_saturday = this_saturday - timedelta(weeks=1)
        last_friday = last_saturday + timedelta(days=6)
        period_start = last_saturday
        period_end = last_friday.replace(hour=23, minute=59, second=59)

    return period_start, period_end


def _slack_get(url: str, params: dict, token: str):
    return requests.get(
        url,
        params=params,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )


def _fetch_all_messages(
    channel_id: str,
    token: str,
    oldest_ts: float,
    latest_ts: float,
) -> tuple[bool, list[dict], str]:
    messages = []
    cursor = None
    while True:
        params: dict = {
            "channel": channel_id,
            "oldest": str(oldest_ts),
            "latest": str(latest_ts),
            "limit": 200,
        }
        if cursor:
            params["cursor"] = cursor

        resp = _slack_get(_SLACK_API_BASE + "conversations.history", params, token)
        if resp.status_code != 200:
            return False, [], f"HTTP {resp.status_code}"
        data = resp.json()
        if not data.get("ok"):
            return False, [], f"Slack API error: {data.get('error', 'unknown')}"

        messages.extend(data.get("messages", []))
        if not data.get("has_more"):
            break
        cursor = (data.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break
        time.sleep(0.5)

    return True, messages, ""


def _fetch_replies(
    channel_id: str,
    token: str,
    thread_ts: str,
    oldest_ts: float | None = None,
    latest_ts: float | None = None,
) -> tuple[bool, list[dict], str]:
    replies = []
    cursor = None
    while True:
        params: dict = {
            "channel": channel_id,
            "ts": thread_ts,
            "limit": 200,
        }
        if oldest_ts is not None:
            params["oldest"] = str(oldest_ts)
        if latest_ts is not None:
            params["latest"] = str(latest_ts)
        if cursor:
            params["cursor"] = cursor

        resp = _slack_get(_SLACK_API_BASE + "conversations.replies", params, token)
        if resp.status_code != 200:
            return False, [], f"HTTP {resp.status_code}"
        data = resp.json()
        if not data.get("ok"):
            return False, [], f"Slack API error: {data.get('error', 'unknown')}"

        msgs = data.get("messages", [])
        if not cursor and msgs:
            msgs = msgs[1:]
        replies.extend(msgs)

        if not data.get("has_more"):
            break
        cursor = (data.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break
        time.sleep(0.5)

    return True, replies, ""


def _format_message(ts: float, user_id: str, text: str, indent: str = "") -> str:
    dt = datetime.fromtimestamp(ts, tz=_JST)
    return f"{indent}[{dt.strftime('%Y-%m-%d %H:%M')}] <{user_id}> {text}"


def fetch_slack_log(
    project: str,
    *,
    week: str = "last",
    since: str | None = None,
    until: str | None = None,
) -> tuple[bool, str]:
    """Slack チャンネルログを取得し projects/<project>/assets/ に保存する。

    week: "last" | "current"（since/until 指定時は無視）
    返り値: (成功フラグ, "取得件数: N件" or エラーメッセージ)
    """
    try:
        if project.startswith("projects/"):
            project = project[len("projects/"):]

        config = _load_project_config(project)
        token = _get_slack_token(config)
        channel_id = _get_slack_channel_id(config)

        if not token:
            return False, "Slack トークンが設定されていません"
        if not channel_id:
            return False, "Slack チャンネル ID が設定されていません"

        period_start, period_end = _calc_period(week, since, until)
        fetch_oldest = period_start - timedelta(days=30)
        oldest_ts = fetch_oldest.timestamp()
        latest_ts = period_end.timestamp()
        period_start_ts = period_start.timestamp()

        ok, messages, err = _fetch_all_messages(channel_id, token, oldest_ts, latest_ts)
        if not ok:
            return False, err

        lines: list[str] = []
        out_of_period_threads: list[str] = []
        count = 0

        for msg in reversed(messages):
            msg_ts = float(msg.get("ts", "0"))
            user_id = msg.get("user") or msg.get("bot_id") or "unknown"
            text = msg.get("text") or ""
            reply_count = msg.get("reply_count") or 0

            in_period = msg_ts >= period_start_ts

            if in_period:
                lines.append(_format_message(msg_ts, user_id, text))
                count += 1

            if reply_count > 0:
                ok_r, replies, err_r = _fetch_replies(
                    channel_id,
                    token,
                    msg["ts"],
                    oldest_ts=period_start_ts,
                    latest_ts=latest_ts,
                )
                if not ok_r:
                    return False, err_r
                time.sleep(0.5)

                period_replies = [
                    r for r in replies if float(r.get("ts", "0")) >= period_start_ts
                ]

                if in_period:
                    for reply in period_replies:
                        r_ts = float(reply.get("ts", "0"))
                        r_user = reply.get("user") or reply.get("bot_id") or "unknown"
                        r_text = reply.get("text") or ""
                        lines.append(_format_message(r_ts, r_user, r_text, indent="    "))
                        count += 1
                elif period_replies:
                    section_lines = [_format_message(msg_ts, user_id, text)]
                    for reply in period_replies:
                        r_ts = float(reply.get("ts", "0"))
                        r_user = reply.get("user") or reply.get("bot_id") or "unknown"
                        r_text = reply.get("text") or ""
                        section_lines.append(_format_message(r_ts, r_user, r_text, indent="    "))
                        count += 1
                    out_of_period_threads.append("\n".join(section_lines))

        if out_of_period_threads:
            lines.append("\n## 期間内のスレッド返信（親メッセージは期間外）")
            for section in out_of_period_threads:
                lines.append(section)

        content = "\n".join(lines) + "\n" if lines else ""

        assets_dir = Path("projects") / project / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        start_str = period_start.strftime("%Y%m%d")
        end_str = period_end.strftime("%Y%m%d")
        out_path = assets_dir / f"{start_str}_{end_str}_Slackのログ.md"
        out_path.write_text(content, encoding="utf-8")

        return True, f"取得件数: {count}件 → {out_path}"
    except Exception as exc:
        return False, str(exc)


def run_auto_update(
    *,
    safe_ratelimit: bool = False,
    dry_run: bool = False,
    week: str = "current",
) -> tuple[bool, str]:
    """有効な全プロジェクトのログを一括取得する。

    safe_ratelimit: API 呼び出し間に sleep を挿入
    dry_run: 対象プロジェクト一覧のみ表示
    """
    projects = _discover_projects()
    lines: list[str] = []

    if not projects:
        return True, "有効なプロジェクトが見つかりませんでした。\n"

    lines.append(f"有効プロジェクト: {len(projects)} 件")
    for p in projects:
        lines.append(f"  - {p['name']} (channel: {p['channel_id']})")

    if dry_run:
        lines.append("dry-run: 実行をスキップします。")
        return True, "\n".join(lines) + "\n"

    succeeded: list[str] = []
    failed: list[str] = []

    for i, p in enumerate(projects):
        name = p["name"]
        ok, out = fetch_slack_log(name, week=week)
        prefix = f"[{i + 1}/{len(projects)}] {name}"
        if ok:
            succeeded.append(name)
            out_lines = [ln for ln in out.splitlines() if ln.strip()]
            summary = out_lines[-1].strip() if out_lines else ""
            lines.append(f"{prefix}: {summary}" if summary else f"{prefix}: 完了")
        else:
            failed.append(name)
            lines.append(f"{prefix}: 失敗")
            if out.strip():
                lines.append(out.strip())

        if safe_ratelimit and i < len(projects) - 1:
            time.sleep(2)

    lines.append(f"\n完了: 成功 {len(succeeded)} / 失敗 {len(failed)}")
    if failed:
        lines.append(f"失敗プロジェクト: {', '.join(failed)}")

    return len(failed) == 0, "\n".join(lines) + "\n"


def post_summary(
    project: str,
    summary_file: str | Path,
    *,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """生成済みサマリーを Slack チャンネルに投稿する。"""
    if project.startswith("projects/"):
        project = project[len("projects/"):]

    summary_path = Path(summary_file)
    if not summary_path.exists():
        return False, f"サマリーファイルが見つかりません: {summary_path}"

    content = summary_path.read_text(encoding="utf-8")

    if dry_run:
        return True, f"[dry-run] {project} へ投稿予定:\n{content}"

    config = _load_project_config(project)
    token = _get_slack_token(config)
    channel_id = _get_slack_channel_id(config)

    if not token:
        return False, "Slack トークンが設定されていません"
    if not channel_id:
        return False, "Slack チャンネル ID が設定されていません"

    try:
        resp = requests.post(
            _SLACK_API_BASE + "chat.postMessage",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={"channel": channel_id, "text": content},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            return False, f"Slack API エラー: {data.get('error', 'unknown')}"
        return True, f"サマリーを投稿しました: {project}"
    except Exception as exc:
        return False, str(exc)
