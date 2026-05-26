from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectConfig:
    """プロジェクトのパス設定。base_dir / project_name でプロジェクトディレクトリを解決する。"""

    project_name: str
    base_dir: Path

    @property
    def project_dir(self) -> Path:
        return self.base_dir / self.project_name

    def validate(self) -> None:
        if not self.project_dir.exists():
            raise FileNotFoundError(
                f"プロジェクトディレクトリが見つかりません: {self.project_dir}"
            )
