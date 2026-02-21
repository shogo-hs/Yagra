"""Local file system implementation of GoldenCaseRepositoryPort (G-20)."""

from __future__ import annotations

import json
from pathlib import Path

from yagra.domain.entities.golden_case import GoldenCase
from yagra.ports.outbound.golden_case_repository import (
    GoldenCaseNotFoundError,
    GoldenCaseRepositoryError,
    GoldenCaseRepositoryPort,
)


class LocalGoldenCaseStore(GoldenCaseRepositoryPort):
    """File-based golden case storage using JSON files.

    Directory structure:
        {base_dir}/
        └── {workflow_name}/
            └── {case_name}.json

    Args:
        base_dir: Root directory for golden case files.
            Defaults to Path(".yagra/golden") relative to cwd.
        indent: JSON indentation spaces. Default 2. None for compact output.

    Examples:
        .yagra/golden/
        └── translate/
            ├── happy-path-translate.json
            └── error-handling-case.json
    """

    def __init__(
        self,
        base_dir: str | Path = Path(".yagra/golden"),
        indent: int | None = 2,
    ) -> None:
        """Initializes the local golden case store.

        Args:
            base_dir: Root directory for golden case storage.
            indent: JSON indentation for human readability. None for compact.
        """
        self._base_dir = Path(base_dir)
        self._indent = indent

    def save(self, case: GoldenCase) -> str:
        """Writes the golden case to a JSON file and returns the file path.

        Args:
            case: The golden case to persist.

        Returns:
            Absolute path to the written JSON file.

        Raises:
            GoldenCaseRepositoryError: If directory creation or file writing fails.
        """
        workflow_dir = self._base_dir / case.workflow_name
        try:
            workflow_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise GoldenCaseRepositoryError(
                f"Failed to create golden case directory '{workflow_dir}': {exc}"
            ) from exc

        file_path = workflow_dir / f"{case.case_name}.json"
        try:
            payload = case.model_dump(mode="json")
            file_path.write_text(
                json.dumps(payload, indent=self._indent, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise GoldenCaseRepositoryError(
                f"Failed to write golden case file '{file_path}': {exc}"
            ) from exc

        return str(file_path.resolve())

    def load(self, workflow_name: str, case_name: str) -> GoldenCase:
        """Loads a golden case from a JSON file.

        Args:
            workflow_name: Name of the workflow (YAML file stem).
            case_name: Name of the golden case.

        Returns:
            The deserialized GoldenCase.

        Raises:
            GoldenCaseNotFoundError: If the file does not exist.
            GoldenCaseRepositoryError: If reading or parsing fails.
        """
        file_path = self._base_dir / workflow_name / f"{case_name}.json"
        if not file_path.exists():
            raise GoldenCaseNotFoundError(f"Golden case not found: {workflow_name}/{case_name}")

        try:
            raw = file_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return GoldenCase.model_validate(data)
        except json.JSONDecodeError as exc:
            raise GoldenCaseRepositoryError(
                f"Invalid JSON in golden case file '{file_path}': {exc}"
            ) from exc
        except OSError as exc:
            raise GoldenCaseRepositoryError(
                f"Failed to read golden case file '{file_path}': {exc}"
            ) from exc

    def list(self, workflow_name: str | None = None) -> list[GoldenCase]:
        """Lists golden cases from the file system.

        Args:
            workflow_name: If provided, only lists cases for this workflow.
                If None, lists all cases across all workflows.

        Returns:
            List of golden cases sorted by workflow_name then case_name.

        Raises:
            GoldenCaseRepositoryError: If reading fails.
        """
        cases: list[GoldenCase] = []

        if not self._base_dir.exists():
            return cases

        if workflow_name is not None:
            workflow_dirs = [self._base_dir / workflow_name]
        else:
            workflow_dirs = sorted(d for d in self._base_dir.iterdir() if d.is_dir())

        for workflow_dir in workflow_dirs:
            if not workflow_dir.exists():
                continue
            for json_file in sorted(workflow_dir.glob("*.json")):
                try:
                    raw = json_file.read_text(encoding="utf-8")
                    data = json.loads(raw)
                    cases.append(GoldenCase.model_validate(data))
                except (json.JSONDecodeError, OSError) as exc:
                    raise GoldenCaseRepositoryError(
                        f"Failed to read golden case file '{json_file}': {exc}"
                    ) from exc

        return cases

    def delete(self, workflow_name: str, case_name: str) -> bool:
        """Deletes a golden case JSON file.

        Args:
            workflow_name: Name of the workflow (YAML file stem).
            case_name: Name of the golden case.

        Returns:
            True if the file was deleted, False if it did not exist.

        Raises:
            GoldenCaseRepositoryError: If deletion fails.
        """
        file_path = self._base_dir / workflow_name / f"{case_name}.json"
        if not file_path.exists():
            return False

        try:
            file_path.unlink()
        except OSError as exc:
            raise GoldenCaseRepositoryError(
                f"Failed to delete golden case file '{file_path}': {exc}"
            ) from exc

        return True

    def exists(self, workflow_name: str, case_name: str) -> bool:
        """Checks whether a golden case file exists.

        Args:
            workflow_name: Name of the workflow (YAML file stem).
            case_name: Name of the golden case.

        Returns:
            True if the JSON file exists, False otherwise.
        """
        file_path = self._base_dir / workflow_name / f"{case_name}.json"
        return file_path.exists()
