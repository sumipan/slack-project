from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Task:
    summary: str
    assignees: list[str]
    due_date: str | None
    description: str | None
    raw_line: str


@dataclass
class ParsedMinutes:
    title: str
    participants: str
    overview: str
    body_text: str
    tasks: list[Task] = field(default_factory=list)


def parse_minutes(
    text: str,
    *,
    section_overview: str = "概要",
    section_meeting: str = "ミーティング",
    section_topics: str = "取り上げられたトピック",
    section_actions: str = "3. アクションアイテム",
    section_actions_alt: str = "アクション・タスク",
    label_participants: str = "参加者",
) -> ParsedMinutes:
    title = ""
    participants = ""
    overview = ""
    body_text = ""
    tasks: list[Task] = []

    title_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if title_m:
        title = title_m.group(1).strip()

    p_label = re.escape(label_participants)
    participants_m = re.search(rf"^\*\s*{p_label}[：:]\s*(.+?)(?=\n|$)", text, re.MULTILINE)
    if participants_m:
        participants = participants_m.group(1).strip()

    s_overview = re.escape(section_overview)
    overview_m = re.search(
        rf"^##\s+{s_overview}\s*$(?:\s*\n)(.+?)(?=\n##\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if overview_m:
        overview = overview_m.group(1).strip()
        overview = re.sub(r"\n+", " ", overview)[:500]

    s_meeting = re.escape(section_meeting)
    s_topics = re.escape(section_topics)
    s_actions = re.escape(section_actions)
    s_actions_alt = re.escape(section_actions_alt)
    action_stop = rf"(?:{s_actions}|{s_actions_alt})"

    body_parts = []
    meeting_m = re.search(
        rf"^##\s+{s_meeting}\s*$(.+?)(?=^##\s+)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if meeting_m:
        body_parts.append(f"## {section_meeting}\n" + meeting_m.group(1).strip())

    rest_m = re.search(
        rf"^##\s+{s_topics}\s*$(.+?)(?=^##\s+{action_stop})",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if rest_m:
        body_parts.append(f"## {section_topics}\n" + rest_m.group(1).strip())

    if body_parts:
        body_text = "\n\n".join(body_parts)
    else:
        fallback_m = re.search(
            rf"^##\s+{s_meeting}\s*$(.+?)(?=^##\s+{action_stop})",
            text,
            re.MULTILINE | re.DOTALL,
        )
        if fallback_m:
            body_text = (f"## {section_meeting}" + fallback_m.group(1)).strip()

    action_section = re.search(
        rf"^##\s+{s_actions}[^\n]*\s*$(?:\s*\n)(?:.*?\n)?\s*```[^\n]*\n(.+?)```",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not action_section:
        action_section = re.search(
            rf"^##\s+{s_actions_alt}[^\n]*\s*$(?:\s*\n)(?:.*?\n)?\s*```[^\n]*\n(.+?)```",
            text,
            re.MULTILINE | re.DOTALL,
        )
    if action_section:
        _extract_tasks(action_section.group(1), tasks)

    return ParsedMinutes(
        title=title,
        participants=participants,
        overview=overview,
        body_text=body_text,
        tasks=tasks,
    )


def _extract_tasks(block: str, tasks: list[Task]) -> None:
    lines = block.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^\s*-\s*\[\s*\]\s*(.+)$", line)
        if not m:
            i += 1
            continue
        content = m.group(1).strip()
        assignees: list[str] = []
        due_date: str | None = None
        description: str | None = None

        if i + 1 < len(lines) and re.match(r"^\s{2,}- ", lines[i + 1]):
            desc_line = lines[i + 1].strip()
            if desc_line.startswith("- "):
                description = desc_line[2:].strip()
            i += 1

        assign_match = re.match(r"^(.+?)[:：]\s*(.+)$", content)
        if assign_match:
            assign_part = assign_match.group(1).strip()
            content = assign_match.group(2).strip()
            for name in re.split(r"[・、]", assign_part):
                n = name.strip()
                if n:
                    assignees.append(n)

        date_m = re.search(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}-\d{1,2})\b", content)
        if date_m:
            due_date = date_m.group(1)

        tasks.append(Task(
            summary=content,
            assignees=assignees if assignees else ["未割り当て"],
            due_date=due_date,
            description=description,
            raw_line=line.strip(),
        ))
        i += 1
