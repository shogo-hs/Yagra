"""Provides save and backup operations for workflow files."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from os import PathLike
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from uuid import uuid4

import yaml


class WorkflowBackupNotFoundError(FileNotFoundError):
    """Exception raised when the specified backup is not found."""


@dataclass(frozen=True, slots=True)
class WorkflowBackupRecord:
    """Holds the backup creation result."""

    backup_id: str
    workflow_backup_path: Path
    ui_state_backup_path: Path


class WorkflowFileStore:
    """Responsible for persisting the workflow and UI sidecar."""

    def __init__(self, backup_root: str | PathLike[str]) -> None:
        """Initializes the save destination configuration.

        Args:
            backup_root: Root directory for storing backups.
        """
        self._backup_root = Path(backup_root).expanduser().resolve()

    def load_workflow(self, workflow_path: str | PathLike[str]) -> dict[str, Any]:
        """Loads the workflow YAML as a dictionary.

        Args:
            workflow_path: Path to the workflow to load.

        Returns:
            The loaded workflow dictionary.

        Raises:
            ValueError: If the YAML is not in dictionary format.
        """
        path = Path(workflow_path).expanduser().resolve()
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = yaml.safe_load(handle)
        except (OSError, yaml.YAMLError) as exc:
            raise ValueError(f"Failed to load workflow: {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"workflow must be a mapping: {path}")
        return dict(payload)

    def load_ui_state(self, ui_state_path: str | PathLike[str]) -> dict[str, Any]:
        """Loads the UI sidecar JSON as a dictionary.

        Args:
            ui_state_path: Path to the UI sidecar to load.

        Returns:
            The loaded UI sidecar dictionary. Returns an empty dictionary if the file does not exist.

        Raises:
            ValueError: If the JSON is not in dictionary format.
        """
        path = Path(ui_state_path).expanduser().resolve()
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Failed to load ui_state: {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"ui_state must be a mapping: {path}")
        return dict(payload)

    def write_workflow_atomic(
        self,
        workflow_path: str | PathLike[str],
        payload: dict[str, Any],
    ) -> None:
        """Saves the workflow YAML using an atomic write.

        Args:
            workflow_path: Path to the workflow to save.
            payload: Workflow data to save.
        """
        text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
        self._atomic_write_text(Path(workflow_path).expanduser().resolve(), text)

    def write_ui_state_atomic(
        self,
        ui_state_path: str | PathLike[str],
        payload: dict[str, Any],
    ) -> None:
        """Saves the UI sidecar JSON using an atomic write.

        Args:
            ui_state_path: Path to the UI sidecar to save.
            payload: UI sidecar data to save.
        """
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        self._atomic_write_text(Path(ui_state_path).expanduser().resolve(), text)

    def write_text_atomic(self, path: str | PathLike[str], text: str) -> None:
        """Saves arbitrary text with an atomic write.

        Args:
            path: Path to save to.
            text: Text string to save.
        """
        self._atomic_write_text(Path(path).expanduser().resolve(), text)

    def create_backup(
        self,
        workflow_path: str | PathLike[str],
        ui_state_path: str | PathLike[str],
        workflow_payload: dict[str, Any],
        ui_state_payload: dict[str, Any],
    ) -> WorkflowBackupRecord:
        """Creates a backup of the workflow and UI sidecar.

        Args:
            workflow_path: Path to the target workflow.
            ui_state_path: Path to the target UI sidecar.
            workflow_payload: Workflow data to back up.
            ui_state_payload: UI sidecar data to back up.

        Returns:
            Information about the created backup.
        """
        workflow_abspath = Path(workflow_path).expanduser().resolve()
        _ = Path(ui_state_path).expanduser().resolve()

        workflow_text = yaml.safe_dump(workflow_payload, sort_keys=False, allow_unicode=True)
        ui_state_text = (
            json.dumps(ui_state_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )

        digest = sha256(f"{workflow_text}\n{ui_state_text}".encode()).hexdigest()[:8]
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S")
        backup_id = f"{timestamp}_{digest}"

        backup_dir = self._backup_root / workflow_abspath.stem
        backup_dir.mkdir(parents=True, exist_ok=True)

        workflow_backup_path = backup_dir / f"{backup_id}.yaml"
        ui_state_backup_path = backup_dir / f"{backup_id}.workflow-ui.json"
        workflow_backup_path.write_text(workflow_text, encoding="utf-8")
        ui_state_backup_path.write_text(ui_state_text, encoding="utf-8")
        self._prune_backups(backup_dir)
        return WorkflowBackupRecord(
            backup_id=backup_id,
            workflow_backup_path=workflow_backup_path,
            ui_state_backup_path=ui_state_backup_path,
        )

    def restore_backup(
        self,
        workflow_path: str | PathLike[str],
        ui_state_path: str | PathLike[str],
        backup_id: str,
    ) -> None:
        """Restores workflow and UI sidecar from the specified backup.

        Args:
            workflow_path: Destination path for the workflow.
            ui_state_path: Destination path for the UI sidecar.
            backup_id: ID of the backup to restore.

        Raises:
            WorkflowBackupNotFoundError: If the backup does not exist.
        """
        workflow_abspath = Path(workflow_path).expanduser().resolve()
        ui_state_abspath = Path(ui_state_path).expanduser().resolve()
        backup_dir = self._backup_root / workflow_abspath.stem

        workflow_backup_path = backup_dir / f"{backup_id}.yaml"
        ui_state_backup_path = backup_dir / f"{backup_id}.workflow-ui.json"
        if not workflow_backup_path.exists() or not ui_state_backup_path.exists():
            raise WorkflowBackupNotFoundError(
                f"backup not found: {backup_id} ({workflow_backup_path}, {ui_state_backup_path})"
            )

        workflow_text = workflow_backup_path.read_text(encoding="utf-8")
        ui_state_text = ui_state_backup_path.read_text(encoding="utf-8")
        self._atomic_write_text(workflow_abspath, workflow_text)
        self._atomic_write_text(ui_state_abspath, ui_state_text)

    def backup_exists(self, workflow_path: str | PathLike[str], backup_id: str) -> bool:
        """Returns whether the specified backup ID exists.

        Args:
            workflow_path: Path to the target workflow.
            backup_id: ID of the backup to check.

        Returns:
            `True` if both the workflow and UI sidecar backups exist.
        """
        workflow_abspath = Path(workflow_path).expanduser().resolve()
        backup_dir = self._backup_root / workflow_abspath.stem
        workflow_backup_path = backup_dir / f"{backup_id}.yaml"
        ui_state_backup_path = backup_dir / f"{backup_id}.workflow-ui.json"
        return workflow_backup_path.exists() and ui_state_backup_path.exists()

    def _atomic_write_text(self, path: Path, text: str) -> None:
        """Performs an atomic write within the same filesystem.

        Args:
            path: Destination path for the write.
            text: Text string to write.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.tmp-",
            suffix=f"-{uuid4().hex}",
            delete=False,
        ) as handle:
            handle.write(text)
            temp_path = Path(handle.name)

        try:
            os.replace(temp_path, path)
        except OSError:
            temp_path.unlink(missing_ok=True)
            raise

    def _prune_backups(self, backup_dir: Path, keep_last: int = 30) -> None:
        """Limits the number of backup generations.

        Args:
            backup_dir: Target backup directory.
            keep_last: Number of generations to retain.
        """
        workflow_backups = sorted(backup_dir.glob("*.yaml"))
        if len(workflow_backups) <= keep_last:
            return

        stale_workflows = workflow_backups[: len(workflow_backups) - keep_last]
        for stale_workflow in stale_workflows:
            stale_ui_state = backup_dir / f"{stale_workflow.stem}.workflow-ui.json"
            stale_workflow.unlink(missing_ok=True)
            stale_ui_state.unlink(missing_ok=True)
