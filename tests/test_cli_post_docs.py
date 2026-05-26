import pytest

from slack_project.cli.post_docs import main


def test_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0


def test_missing_required_arg_exits_two():
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2


def test_not_implemented_returns_one(capsys):
    result = main(["--minutes", "/tmp/test.md"])
    assert result == 1
    captured = capsys.readouterr()
    assert captured.err != ""


def test_dry_run_flag(capsys):
    result = main(["--minutes", "/tmp/test.md", "--dry-run"])
    assert result == 1


def test_main_returns_int():
    result = main(["--minutes", "/tmp/test.md"])
    assert isinstance(result, int)
