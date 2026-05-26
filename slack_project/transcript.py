from __future__ import annotations

import re
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def parse_source_path(path: str) -> tuple[str, str, str]:
    """文字起こしパスから (project, date, meeting) を抽出する。

    path: "resources/<project>/<YYYY-MM-DD>/<meeting>/..." 形式
    Raises: ValueError（パス形式不正または日付が YYYY-MM-DD でない場合）
    """
    parts = Path(path).parts
    try:
        idx = parts.index("resources")
        project = parts[idx + 1]
        date = parts[idx + 2]
        meeting = parts[idx + 3]
    except (ValueError, IndexError):
        raise ValueError(
            f"パスが期待する形式でありません: {path}\n"
            "期待する形式: resources/<project>/<date>/<meeting>/..."
        )

    if not re.match(r"\d{4}-\d{2}-\d{2}$", date):
        raise ValueError(
            f"日付形式が不正です (YYYY-MM-DD 必要): {date} (パス: {path})"
        )

    return project, date, meeting


def detect_transcript_type(content: str) -> str:
    """文字起こし内容からソース種別を判定する。

    Returns: "teams" | "zoom" | "unknown"
    """
    if re.search(r"^#{0,6}\s*(要約|チャプター|行動項目)", content, re.MULTILINE):
        return "teams"
    if re.search(r"^WEBVTT|Zoom\s+Meeting", content, re.MULTILINE):
        return "zoom"
    return "unknown"


def command_file(project: str, meeting: str) -> Path:
    """スキルコマンドファイルのパスを返す。

    常に skills/project-minutes/SKILL.md を返す（引数は将来拡張用）。
    """
    return _PACKAGE_ROOT / "skills" / "project-minutes" / "SKILL.md"
