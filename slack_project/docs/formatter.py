from __future__ import annotations

import re

from slack_project.docs.parser import Task

SECTION_TEXT_MAX = 3000


def format_head_blocks(
    overview: str, meeting_title: str, participants_line: str,
) -> list[dict]:
    """チャンネル冒頭投稿用の Block Kit JSON（section + context）を返す。"""
    overview_trim = overview[:400] + ("…" if len(overview) > 400 else "")
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{meeting_title}*\n\n{overview_trim}",
            },
        },
    ]
    if participants_line:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"*参加者:* {participants_line}"}],
        })
    return blocks


def format_body_blocks(meeting_title: str, body_text: str) -> list[dict]:
    """スレッド用の議事録本文 Block Kit JSON（header + section + divider + 詳細）を返す。"""
    date_line, participants_in_body, topics_mrkdwn, detail_sections = _parse_body_for_blocks(body_text)

    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": meeting_title, "emoji": True}},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*日時:* {date_line or '（記載なし）'}\n*参加者:* {participants_in_body or '（記載なし）'}",
            },
        },
        {"type": "divider"},
    ]

    if topics_mrkdwn:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*取り上げられたトピック*\n{topics_mrkdwn}"},
        })
        blocks.append({"type": "divider"})

    for title, content in detail_sections:
        if not content and not title:
            continue
        content = re.sub(r"^\*\s+", "", content)
        content = re.sub(r"\n\*\s+", "\n\n", content)
        section_text = f"*{title}*\n\n{content}" if title else content
        if len(section_text) > SECTION_TEXT_MAX:
            section_text = section_text[: SECTION_TEXT_MAX - 1] + "…"
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": section_text},
        })

    return blocks


def format_action_blocks(
    tasks: list[Task], members_map: dict[str, str] | None = None,
) -> list[dict]:
    """スレッド用のアクション項目 Block Kit JSON を返す。
    members_map: {表示名: Slack UID}。None 時は名前をそのまま表示。"""
    lines = ["*アクション項目*"]
    for t in tasks:
        mentions = []
        for a in t.assignees:
            if a == "未割り当て" or members_map is None:
                mentions.append(a)
            else:
                uid = members_map.get(a)
                mentions.append(f"<@{uid}>" if uid else a)
        line = " ".join(mentions) + " " + t.summary
        if t.due_date:
            line += f"（期日: {t.due_date}）"
        lines.append(":white_square: " + line)
    text = "\n\n".join(lines)
    return [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]


def fallback_text(blocks: list[dict]) -> str:
    """blocks から通知用の短いテキスト（100 文字以内）を生成する。"""
    for b in blocks:
        if b.get("type") == "section" and "text" in b:
            t = b["text"]
            if isinstance(t, dict) and t.get("type") == "mrkdwn":
                raw = t.get("text", "")
                return (raw.replace("*", "").strip()[:100] + "…") if len(raw) > 100 else raw
        if b.get("type") == "header" and "text" in b:
            return b["text"].get("text", "議事録")[:80]
    return "議事録投稿"


def _parse_body_for_blocks(body_text: str) -> tuple[str, str, str, list[tuple[str, str]]]:
    date_line = ""
    participants_in_body = ""
    topics_mrkdwn = ""
    detail_sections: list[tuple[str, str]] = []

    date_m = re.search(r"^\*\s*日時[：:]\s*(.+?)(?=\n|$)", body_text, re.MULTILINE)
    if date_m:
        date_line = date_m.group(1).strip()
    part_m = re.search(r"^\*\s*参加者[：:]\s*(.+?)(?=\n|$)", body_text, re.MULTILINE)
    if part_m:
        participants_in_body = part_m.group(1).strip()

    topics_match = re.search(
        r"^##\s+取り上げられたトピック\s*\n(.+?)(?=^##\s+詳細|\Z)",
        body_text,
        re.MULTILINE | re.DOTALL,
    )
    if topics_match:
        topic_lines = [
            ln.strip().replace("* ", "", 1)
            for ln in topics_match.group(1).strip().split("\n")
            if ln.strip().startswith("*")
        ]
        topics_mrkdwn = "\n".join("・" + ln for ln in topic_lines if ln)

    details_match = re.search(r"^##\s+詳細\s*\n(.*)", body_text, re.MULTILINE | re.DOTALL)
    if details_match:
        rest = details_match.group(1).strip()
        parts = re.split(r"\n###\s+", rest)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if part.startswith("### "):
                part = part[4:].strip()
            lines = part.split("\n")
            first_line = lines[0].strip()
            content = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
            if first_line and not first_line.startswith("*"):
                detail_sections.append((first_line, content))
            elif content:
                detail_sections.append(("", part))

    return date_line, participants_in_body, topics_mrkdwn, detail_sections
