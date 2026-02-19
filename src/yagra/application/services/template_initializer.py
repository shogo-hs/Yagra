"""Service for initializing workflows from templates."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class TemplateInfo:
    """Metadata for a template.

    Attributes:
        name: Template name (directory name).
        description: Use-case description (loaded from template.yaml).
        use_case: Target use case (loaded from template.yaml).
    """

    name: str
    description: str
    use_case: str


class TemplateNotFoundError(ValueError):
    """Exception raised when the specified template does not exist."""

    def __init__(self, template_name: str, available_templates: Sequence[str]) -> None:
        """Initializes the exception.

        Args:
            template_name: Specified template name.
            available_templates: List of available templates.
        """
        available_str = ", ".join(available_templates)
        super().__init__(
            f"Template '{template_name}' not found. Available templates: {available_str}"
        )
        self.template_name = template_name
        self.available_templates = list(available_templates)


class FileAlreadyExistsError(FileExistsError):
    """Exception raised when a file already exists at the output destination."""

    def __init__(self, existing_files: Sequence[Path]) -> None:
        """Initializes the exception.

        Args:
            existing_files: List of files that already exist.
        """
        files_str = "\n".join(f"  - {f}" for f in existing_files)
        super().__init__(
            f"Files already exist at the output destination:\n{files_str}\n"
            f"Use the --force flag to overwrite."
        )
        self.existing_files = list(existing_files)


def list_templates() -> list[str]:
    """Returns a list of available templates.

    Returns:
        List of template names.
    """
    templates_dir = _get_templates_root()
    if not templates_dir.exists():
        return []

    templates = []
    for item in templates_dir.iterdir():
        if item.is_dir() and (item / "workflow.yaml").exists():
            templates.append(item.name)

    return sorted(templates)


def list_templates_with_info() -> list[TemplateInfo]:
    """Returns a list of available templates with metadata.

    Loads metadata from `template.yaml` in each template directory.
    Returns only the template name if `template.yaml` does not exist.

    Returns:
        List of template metadata.
    """
    templates_dir = _get_templates_root()
    if not templates_dir.exists():
        return []

    infos: list[TemplateInfo] = []
    for item in sorted(templates_dir.iterdir()):
        if not (item.is_dir() and (item / "workflow.yaml").exists()):
            continue

        meta_path = item / "template.yaml"
        if meta_path.exists():
            try:
                with meta_path.open(encoding="utf-8") as f:
                    meta = yaml.safe_load(f) or {}
                description = str(meta.get("description", ""))
                use_case = str(meta.get("use_case", ""))
            except (yaml.YAMLError, OSError):
                description = ""
                use_case = ""
        else:
            description = ""
            use_case = ""

        infos.append(TemplateInfo(name=item.name, description=description, use_case=use_case))

    return infos


def initialize_from_template(
    template_name: str,
    output_dir: Path,
    force: bool = False,
) -> None:
    """Initializes a workflow from the specified template.

    Args:
        template_name: Template name (e.g. "branch", "loop", "rag").
        output_dir: Absolute path to the output directory.
        force: If True, overwrites existing files.

    Raises:
        TemplateNotFoundError: If the specified template does not exist.
        FileAlreadyExistsError: If files already exist at the output destination and force=False.
    """
    available_templates = list_templates()
    if template_name not in available_templates:
        raise TemplateNotFoundError(template_name, available_templates)

    template_dir = _get_templates_root() / template_name
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check for existing files
    if not force:
        existing_files = _check_existing_files(template_dir, output_dir)
        if existing_files:
            raise FileAlreadyExistsError(existing_files)

    # Copy template files (excluding template.yaml)
    _copy_template_files(template_dir, output_dir)


def _get_templates_root() -> Path:
    """Returns the path to the template root directory.

    Returns:
        Absolute path to the template root directory.
    """
    return Path(__file__).parent.parent.parent / "templates"


def _check_existing_files(template_dir: Path, output_dir: Path) -> list[Path]:
    """Checks for files that already exist at the output destination.

    Args:
        template_dir: Template directory.
        output_dir: Output destination directory.

    Returns:
        List of files that already exist.
    """
    existing_files = []

    for item in template_dir.rglob("*"):
        if item.is_file() and item.name != "template.yaml":
            relative_path = item.relative_to(template_dir)
            output_path = output_dir / relative_path
            if output_path.exists():
                existing_files.append(output_path)

    return existing_files


def _copy_template_files(template_dir: Path, output_dir: Path) -> None:
    """Copies template files to the output destination.

    Excludes `template.yaml` (metadata file) from the copy targets.

    Args:
        template_dir: Template directory.
        output_dir: Output destination directory.
    """
    for item in template_dir.rglob("*"):
        if item.is_file() and item.name != "template.yaml":
            relative_path = item.relative_to(template_dir)
            output_path = output_dir / relative_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, output_path)
