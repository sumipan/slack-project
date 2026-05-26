import pytest

from slack_project.cli.fetch_logs import main


def test_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0


def test_missing_required_arg_exits_two():
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2


def test_not_implemented_returns_one(capsys):
    result = main(["--project", "test"])
    assert result == 1
    captured = capsys.readouterr()
    assert captured.err != ""


def test_from_date_flag(capsys):
    result = main(["--project", "test", "--from-date", "2024-01-01"])
    assert result == 1


def test_safe_ratelimit_flag(capsys):
    result = main(["--project", "test", "--safe-ratelimit"])
    assert result == 1


def test_main_returns_int():
    result = main(["--project", "test"])
    assert isinstance(result, int)
