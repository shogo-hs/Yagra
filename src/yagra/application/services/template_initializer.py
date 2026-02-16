"""テンプレートからワークフローを初期化するサービス。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


class TemplateNotFoundError(ValueError):
    """指定されたテンプレートが存在しない場合の例外。"""

    def __init__(self, template_name: str, available_templates: Sequence[str]) -> None:
        """例外を初期化する。

        Args:
            template_name: 指定されたテンプレート名。
            available_templates: 利用可能なテンプレート一覧。
        """
        available_str = ", ".join(available_templates)
        super().__init__(
            f"テンプレート '{template_name}' が見つかりません。"
            f"利用可能なテンプレート: {available_str}"
        )
        self.template_name = template_name
        self.available_templates = list(available_templates)


class FileAlreadyExistsError(FileExistsError):
    """出力先にファイルが既に存在する場合の例外。"""

    def __init__(self, existing_files: Sequence[Path]) -> None:
        """例外を初期化する。

        Args:
            existing_files: 既に存在するファイルのリスト。
        """
        files_str = "\n".join(f"  - {f}" for f in existing_files)
        super().__init__(
            f"出力先に既にファイルが存在します:\n{files_str}\n"
            f"上書きする場合は --force フラグを使用してください。"
        )
        self.existing_files = list(existing_files)


def list_templates() -> list[str]:
    """利用可能なテンプレート一覧を返す。

    Returns:
        テンプレート名のリスト。
    """
    templates_dir = _get_templates_root()
    if not templates_dir.exists():
        return []

    templates = []
    for item in templates_dir.iterdir():
        if item.is_dir() and (item / "workflow.yaml").exists():
            templates.append(item.name)

    return sorted(templates)


def initialize_from_template(
    template_name: str,
    output_dir: Path,
    force: bool = False,
) -> None:
    """指定されたテンプレートからワークフローを初期化する。

    Args:
        template_name: テンプレート名（例: "branch", "loop", "rag"）。
        output_dir: 出力先ディレクトリの絶対パス。
        force: True の場合、既存ファイルを上書きする。

    Raises:
        TemplateNotFoundError: 指定されたテンプレートが存在しない場合。
        FileAlreadyExistsError: 出力先に既にファイルが存在し、force=False の場合。
    """
    available_templates = list_templates()
    if template_name not in available_templates:
        raise TemplateNotFoundError(template_name, available_templates)

    template_dir = _get_templates_root() / template_name
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # 既存ファイルチェック
    if not force:
        existing_files = _check_existing_files(template_dir, output_dir)
        if existing_files:
            raise FileAlreadyExistsError(existing_files)

    # テンプレートファイルをコピー
    _copy_template_files(template_dir, output_dir)


def _get_templates_root() -> Path:
    """テンプレートルートディレクトリのパスを返す。

    Returns:
        テンプレートルートディレクトリの絶対パス。
    """
    return Path(__file__).parent.parent.parent / "templates"


def _check_existing_files(template_dir: Path, output_dir: Path) -> list[Path]:
    """出力先に既に存在するファイルをチェックする。

    Args:
        template_dir: テンプレートディレクトリ。
        output_dir: 出力先ディレクトリ。

    Returns:
        既に存在するファイルのリスト。
    """
    existing_files = []

    for item in template_dir.rglob("*"):
        if item.is_file():
            relative_path = item.relative_to(template_dir)
            output_path = output_dir / relative_path
            if output_path.exists():
                existing_files.append(output_path)

    return existing_files


def _copy_template_files(template_dir: Path, output_dir: Path) -> None:
    """テンプレートファイルを出力先にコピーする。

    Args:
        template_dir: テンプレートディレクトリ。
        output_dir: 出力先ディレクトリ。
    """
    for item in template_dir.rglob("*"):
        if item.is_file():
            relative_path = item.relative_to(template_dir)
            output_path = output_dir / relative_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, output_path)
