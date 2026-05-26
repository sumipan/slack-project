import tempfile
from pathlib import Path

import pytest

from slack_project.config import ProjectConfig


def test_project_dir_property():
    cfg = ProjectConfig(project_name="test", base_dir=Path("/tmp"))
    assert cfg.project_dir == Path("/tmp/test")


def test_validate_raises_when_dir_missing():
    cfg = ProjectConfig(project_name="nonexistent_xyzzy", base_dir=Path("/tmp"))
    with pytest.raises(FileNotFoundError) as exc_info:
        cfg.validate()
    assert "/tmp/nonexistent_xyzzy" in str(exc_info.value)


def test_validate_passes_when_dir_exists():
    with tempfile.TemporaryDirectory() as base:
        base_path = Path(base)
        project_dir = base_path / "myproject"
        project_dir.mkdir()
        cfg = ProjectConfig(project_name="myproject", base_dir=base_path)
        cfg.validate()  # should not raise
