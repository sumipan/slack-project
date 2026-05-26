import pytest
from pathlib import Path

from slack_project.transcript import parse_source_path, detect_transcript_type, command_file


class TestParseSourcePath:
    def test_normal(self):
        project, date, meeting = parse_source_path(
            "resources/proj/2025-01-15/mtg/transcript.md"
        )
        assert project == "proj"
        assert date == "2025-01-15"
        assert meeting == "mtg"

    def test_nested_path(self):
        project, date, meeting = parse_source_path(
            "/absolute/resources/my-project/2026-05-26/standup/transcript.md"
        )
        assert project == "my-project"
        assert date == "2026-05-26"
        assert meeting == "standup"

    def test_invalid_path_no_resources(self):
        with pytest.raises(ValueError):
            parse_source_path("invalid/path/here")

    def test_invalid_path_too_few_parts(self):
        with pytest.raises(ValueError):
            parse_source_path("resources/proj")

    def test_invalid_date_format(self):
        with pytest.raises(ValueError, match="日付形式が不正"):
            parse_source_path("resources/proj/not-a-date/mtg/transcript.md")

    def test_invalid_date_partial(self):
        with pytest.raises(ValueError, match="日付形式が不正"):
            parse_source_path("resources/proj/2025-1-5/mtg/transcript.md")


class TestDetectTranscriptType:
    def test_teams_youyaku(self):
        assert detect_transcript_type("## 要約\nテスト内容") == "teams"

    def test_teams_chapter(self):
        assert detect_transcript_type("チャプター\n本文") == "teams"

    def test_teams_action_items(self):
        assert detect_transcript_type("行動項目\n- タスク") == "teams"

    def test_zoom_webvtt(self):
        assert detect_transcript_type("WEBVTT\n00:00:01.000 --> 00:00:05.000") == "zoom"

    def test_zoom_meeting(self):
        assert detect_transcript_type("Zoom Meeting Recording\n---") == "zoom"

    def test_unknown_empty(self):
        assert detect_transcript_type("") == "unknown"

    def test_unknown_generic(self):
        assert detect_transcript_type("Just some random text here.") == "unknown"


class TestCommandFile:
    def test_returns_path(self):
        result = command_file("proj", "mtg")
        assert isinstance(result, Path)

    def test_path_ends_correctly(self):
        result = command_file("proj", "mtg")
        parts = result.parts
        assert "skills" in parts
        idx = list(parts).index("skills")
        assert parts[idx + 1] == "project-minutes"
        assert parts[idx + 2] == "SKILL.md"
