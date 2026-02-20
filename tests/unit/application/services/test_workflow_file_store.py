"""Unit tests for WorkflowFileStore."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from yagra.application.services.workflow_file_store import (
    WorkflowBackupNotFoundError,
    WorkflowBackupRecord,
    WorkflowFileStore,
)


class TestLoadWorkflow:
    """Tests for WorkflowFileStore.load_workflow."""

    def test_load_valid_yaml(self, tmp_path: Path) -> None:
        workflow_path = tmp_path / "workflow.yaml"
        data = {"name": "test", "steps": ["a", "b"]}
        workflow_path.write_text(yaml.safe_dump(data), encoding="utf-8")

        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        result = store.load_workflow(workflow_path)

        assert result == data

    def test_load_workflow_raises_value_error_on_os_error(self, tmp_path: Path) -> None:
        """Covers lines 59-60: OSError during file open raises ValueError."""
        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        non_existent = tmp_path / "nonexistent.yaml"

        with pytest.raises(ValueError, match="Failed to load workflow"):
            store.load_workflow(non_existent)

    def test_load_workflow_raises_value_error_on_yaml_error(self, tmp_path: Path) -> None:
        """Covers lines 59-60: YAMLError during parsing raises ValueError."""
        workflow_path = tmp_path / "bad.yaml"
        # Write YAML that causes a parse error (tab characters cause scanner error)
        workflow_path.write_text("key: [\ninvalid: yaml: :", encoding="utf-8")

        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        with pytest.raises(ValueError, match="Failed to load workflow"):
            store.load_workflow(workflow_path)

    def test_load_workflow_raises_value_error_on_non_dict(self, tmp_path: Path) -> None:
        """Covers line 62: non-dict payload raises ValueError."""
        workflow_path = tmp_path / "list.yaml"
        workflow_path.write_text(yaml.safe_dump(["item1", "item2"]), encoding="utf-8")

        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        with pytest.raises(ValueError, match="workflow must be a mapping"):
            store.load_workflow(workflow_path)


class TestLoadUiState:
    """Tests for WorkflowFileStore.load_ui_state."""

    def test_load_valid_json(self, tmp_path: Path) -> None:
        ui_path = tmp_path / "ui.json"
        data = {"key": "value"}
        ui_path.write_text(json.dumps(data), encoding="utf-8")

        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        result = store.load_ui_state(ui_path)

        assert result == data

    def test_load_returns_empty_dict_when_file_not_exists(self, tmp_path: Path) -> None:
        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        result = store.load_ui_state(tmp_path / "missing.json")
        assert result == {}

    def test_load_ui_state_raises_value_error_on_os_error(self, tmp_path: Path) -> None:
        """Covers lines 82-83: OSError during read raises ValueError."""
        ui_path = tmp_path / "ui.json"
        ui_path.write_text(json.dumps({"x": 1}), encoding="utf-8")

        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        with patch("pathlib.Path.read_text", side_effect=OSError("IO error")):
            with pytest.raises(ValueError, match="Failed to load ui_state"):
                store.load_ui_state(ui_path)

    def test_load_ui_state_raises_value_error_on_invalid_json(self, tmp_path: Path) -> None:
        """Covers lines 82-83: JSONDecodeError during parsing raises ValueError."""
        ui_path = tmp_path / "bad.json"
        ui_path.write_text("not valid json {{{", encoding="utf-8")

        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        with pytest.raises(ValueError, match="Failed to load ui_state"):
            store.load_ui_state(ui_path)

    def test_load_ui_state_raises_value_error_on_non_dict(self, tmp_path: Path) -> None:
        """Covers line 85: non-dict JSON payload raises ValueError."""
        ui_path = tmp_path / "list.json"
        ui_path.write_text(json.dumps(["item1", "item2"]), encoding="utf-8")

        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        with pytest.raises(ValueError, match="ui_state must be a mapping"):
            store.load_ui_state(ui_path)


class TestWriteAtomicMethods:
    """Tests for write_workflow_atomic, write_ui_state_atomic, and write_text_atomic."""

    def test_write_workflow_atomic_creates_file(self, tmp_path: Path) -> None:
        """Covers lines 99-100: write_workflow_atomic writes YAML content atomically."""
        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        dest = tmp_path / "workflow.yaml"
        payload = {"name": "my_flow", "steps": [1, 2, 3]}

        store.write_workflow_atomic(dest, payload)

        assert dest.exists()
        loaded = yaml.safe_load(dest.read_text(encoding="utf-8"))
        assert loaded == payload

    def test_write_ui_state_atomic_creates_file(self, tmp_path: Path) -> None:
        """Covers lines 113-114: write_ui_state_atomic writes JSON content atomically."""
        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        dest = tmp_path / "ui.json"
        payload = {"theme": "dark", "zoom": 1.5}

        store.write_ui_state_atomic(dest, payload)

        assert dest.exists()
        loaded = json.loads(dest.read_text(encoding="utf-8"))
        assert loaded == payload

    def test_write_text_atomic_creates_file(self, tmp_path: Path) -> None:
        """Covers line 123: write_text_atomic writes arbitrary text atomically."""
        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        dest = tmp_path / "notes.txt"

        store.write_text_atomic(dest, "hello world\n")

        assert dest.exists()
        assert dest.read_text(encoding="utf-8") == "hello world\n"


class TestCreateAndRestoreBackup:
    """Tests for WorkflowFileStore.create_backup and restore_backup."""

    def test_create_backup_returns_record(self, tmp_path: Path) -> None:
        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        workflow_path = tmp_path / "workflow.yaml"
        ui_state_path = tmp_path / "ui.json"

        record = store.create_backup(
            workflow_path=workflow_path,
            ui_state_path=ui_state_path,
            workflow_payload={"name": "test"},
            ui_state_payload={"x": 1},
        )

        assert isinstance(record, WorkflowBackupRecord)
        assert record.workflow_backup_path.exists()
        assert record.ui_state_backup_path.exists()

    def test_restore_backup_raises_when_not_found(self, tmp_path: Path) -> None:
        """Covers line 192: backup not found raises WorkflowBackupNotFoundError."""
        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        workflow_path = tmp_path / "workflow.yaml"
        ui_state_path = tmp_path / "ui.json"

        with pytest.raises(WorkflowBackupNotFoundError, match="backup not found"):
            store.restore_backup(
                workflow_path=workflow_path,
                ui_state_path=ui_state_path,
                backup_id="nonexistent_backup_id",
            )

    def test_restore_backup_succeeds(self, tmp_path: Path) -> None:
        """Restore writes the backup content back to the original paths."""
        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        workflow_path = tmp_path / "workflow.yaml"
        ui_state_path = tmp_path / "ui.json"

        workflow_payload = {"name": "restored"}
        ui_state_payload = {"restored": True}

        record = store.create_backup(
            workflow_path=workflow_path,
            ui_state_path=ui_state_path,
            workflow_payload=workflow_payload,
            ui_state_payload=ui_state_payload,
        )

        store.restore_backup(
            workflow_path=workflow_path,
            ui_state_path=ui_state_path,
            backup_id=record.backup_id,
        )

        assert workflow_path.exists()
        assert ui_state_path.exists()


class TestAtomicWriteText:
    """Tests for WorkflowFileStore._atomic_write_text."""

    def test_atomic_write_raises_os_error_on_replace_failure(self, tmp_path: Path) -> None:
        """Covers lines 238-240: os.replace failure unlinks temp file and re-raises."""
        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        dest = tmp_path / "output.txt"

        with patch("os.replace", side_effect=OSError("Cross-device rename")):
            with pytest.raises(OSError, match="Cross-device rename"):
                store._atomic_write_text(dest, "hello")

        # The temp file should have been cleaned up
        temp_files = list(tmp_path.glob(".output.txt.tmp-*"))
        assert len(temp_files) == 0

    def test_atomic_write_succeeds(self, tmp_path: Path) -> None:
        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        dest = tmp_path / "output.txt"
        store._atomic_write_text(dest, "hello world")
        assert dest.read_text(encoding="utf-8") == "hello world"


class TestPruneBackups:
    """Tests for WorkflowFileStore._prune_backups."""

    def test_prune_removes_stale_backups_when_exceeding_keep_last(self, tmp_path: Path) -> None:
        """Covers lines 253-257: stale backups are removed when count > keep_last."""
        backup_dir = tmp_path / "backups" / "workflow"
        backup_dir.mkdir(parents=True)

        # Create 35 pairs of backup files (> default keep_last=30)
        created_stems = []
        for i in range(35):
            stem = f"2026010{i:02d}120000_abcd{i:04d}"
            created_stems.append(stem)
            (backup_dir / f"{stem}.yaml").write_text("data", encoding="utf-8")
            (backup_dir / f"{stem}.workflow-ui.json").write_text("{}", encoding="utf-8")

        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        store._prune_backups(backup_dir, keep_last=30)

        remaining_yamls = sorted(backup_dir.glob("*.yaml"))
        assert len(remaining_yamls) == 30

        # The first 5 (oldest) should have been deleted
        for stem in created_stems[:5]:
            assert not (backup_dir / f"{stem}.yaml").exists()
            assert not (backup_dir / f"{stem}.workflow-ui.json").exists()

        # The last 30 should still exist
        for stem in created_stems[5:]:
            assert (backup_dir / f"{stem}.yaml").exists()

    def test_prune_does_nothing_when_within_keep_last(self, tmp_path: Path) -> None:
        """No files are removed when count <= keep_last."""
        backup_dir = tmp_path / "backups" / "workflow"
        backup_dir.mkdir(parents=True)

        for i in range(5):
            stem = f"2026010{i}120000_abcd{i:04d}"
            (backup_dir / f"{stem}.yaml").write_text("data", encoding="utf-8")
            (backup_dir / f"{stem}.workflow-ui.json").write_text("{}", encoding="utf-8")

        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        store._prune_backups(backup_dir, keep_last=30)

        assert len(list(backup_dir.glob("*.yaml"))) == 5


class TestBackupExists:
    """Tests for WorkflowFileStore.backup_exists."""

    def test_backup_exists_returns_true_when_both_files_present(self, tmp_path: Path) -> None:
        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        workflow_path = tmp_path / "my_flow.yaml"
        ui_state_path = tmp_path / "my_flow.json"

        record = store.create_backup(
            workflow_path=workflow_path,
            ui_state_path=ui_state_path,
            workflow_payload={"name": "test"},
            ui_state_payload={},
        )

        assert store.backup_exists(workflow_path, record.backup_id) is True

    def test_backup_exists_returns_false_when_missing(self, tmp_path: Path) -> None:
        store = WorkflowFileStore(backup_root=tmp_path / "backups")
        workflow_path = tmp_path / "my_flow.yaml"
        assert store.backup_exists(workflow_path, "nonexistent") is False
