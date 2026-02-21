"""Unit tests for LocalGoldenCaseStore (G-20)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from yagra.adapters.outbound.local_golden_case_store import LocalGoldenCaseStore
from yagra.domain.entities.comparison import ComparisonStrategy
from yagra.domain.entities.golden_case import GoldenCase, NodeSnapshot
from yagra.ports.outbound.golden_case_repository import (
    GoldenCaseNotFoundError,
    GoldenCaseRepositoryError,
)


def _make_golden_case(
    case_name: str = "happy-path",
    workflow_name: str = "translate",
    **overrides: Any,
) -> GoldenCase:
    now = datetime.now(tz=UTC)
    defaults: dict[str, Any] = {
        "schema_version": "1.0",
        "case_name": case_name,
        "description": "Test case",
        "workflow_name": workflow_name,
        "workflow_path": f"workflows/{workflow_name}.yaml",
        "created_at": now,
        "source_run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "initial_state": {"text": "hello"},
        "final_state": {"text": "hello", "translated": "こんにちは"},
        "execution_path": ["translate_node"],
        "node_snapshots": {
            "translate_node": NodeSnapshot(
                node_id="translate_node",
                handler="llm",
                is_llm_handler=True,
                input_snapshot={"text": "hello"},
                output_snapshot={"translated": "こんにちは"},
                comparison_strategy=ComparisonStrategy.AUTO,
            ),
        },
        "metadata": {},
    }
    defaults.update(overrides)
    return GoldenCase(**defaults)


class TestLocalGoldenCaseStoreSave:
    def test_save_creates_file(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        case = _make_golden_case()
        path_str = store.save(case)
        assert Path(path_str).exists()

    def test_save_creates_workflow_subdirectory(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        case = _make_golden_case(workflow_name="my_workflow")
        store.save(case)
        assert (tmp_path / "my_workflow").is_dir()

    def test_save_filename_matches_case_name(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        case = _make_golden_case(case_name="my-test-case")
        path_str = store.save(case)
        assert Path(path_str).name == "my-test-case.json"

    def test_save_returns_absolute_path(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        case = _make_golden_case()
        path_str = store.save(case)
        assert Path(path_str).is_absolute()

    def test_saved_json_is_valid(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        case = _make_golden_case()
        path_str = store.save(case)
        content = json.loads(Path(path_str).read_text(encoding="utf-8"))
        assert content["schema_version"] == "1.0"
        assert content["case_name"] == "happy-path"
        assert content["workflow_name"] == "translate"

    def test_save_overwrites_existing(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        case1 = _make_golden_case(description="first")
        case2 = _make_golden_case(description="second")
        store.save(case1)
        path_str = store.save(case2)
        content = json.loads(Path(path_str).read_text(encoding="utf-8"))
        assert content["description"] == "second"

    def test_compact_mode(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path, indent=None)
        case = _make_golden_case()
        path_str = store.save(case)
        content = Path(path_str).read_text(encoding="utf-8")
        assert "\n  " not in content

    def test_save_raises_on_mkdir_failure(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        case = _make_golden_case()
        with patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied")):
            with pytest.raises(
                GoldenCaseRepositoryError, match="Failed to create golden case directory"
            ):
                store.save(case)

    def test_save_raises_on_write_failure(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        case = _make_golden_case()
        with patch("pathlib.Path.write_text", side_effect=OSError("Disk full")):
            with pytest.raises(GoldenCaseRepositoryError, match="Failed to write golden case file"):
                store.save(case)


class TestLocalGoldenCaseStoreLoad:
    def test_load_returns_saved_case(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        case = _make_golden_case()
        store.save(case)
        loaded = store.load("translate", "happy-path")
        assert loaded.case_name == "happy-path"
        assert loaded.workflow_name == "translate"

    def test_load_raises_not_found(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        with pytest.raises(GoldenCaseNotFoundError, match="Golden case not found"):
            store.load("translate", "nonexistent")

    def test_load_raises_on_invalid_json(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        workflow_dir = tmp_path / "translate"
        workflow_dir.mkdir(parents=True)
        (workflow_dir / "bad.json").write_text("not valid json", encoding="utf-8")
        with pytest.raises(GoldenCaseRepositoryError, match="Invalid JSON"):
            store.load("translate", "bad")

    def test_load_preserves_node_snapshots(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        case = _make_golden_case()
        store.save(case)
        loaded = store.load("translate", "happy-path")
        assert "translate_node" in loaded.node_snapshots
        snap = loaded.node_snapshots["translate_node"]
        assert snap.handler == "llm"
        assert snap.is_llm_handler is True


class TestLocalGoldenCaseStoreList:
    def test_list_empty_returns_empty(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        assert store.list() == []

    def test_list_nonexistent_base_dir(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path / "nonexistent")
        assert store.list() == []

    def test_list_all_cases(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        store.save(_make_golden_case(case_name="case-a", workflow_name="wf1"))
        store.save(_make_golden_case(case_name="case-b", workflow_name="wf2"))
        cases = store.list()
        assert len(cases) == 2

    def test_list_filtered_by_workflow(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        store.save(_make_golden_case(case_name="case-a", workflow_name="wf1"))
        store.save(_make_golden_case(case_name="case-b", workflow_name="wf2"))
        cases = store.list(workflow_name="wf1")
        assert len(cases) == 1
        assert cases[0].workflow_name == "wf1"

    def test_list_nonexistent_workflow_returns_empty(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        store.save(_make_golden_case())
        assert store.list(workflow_name="nonexistent") == []

    def test_list_sorted_order(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        store.save(_make_golden_case(case_name="case-z", workflow_name="alpha"))
        store.save(_make_golden_case(case_name="case-a", workflow_name="alpha"))
        store.save(_make_golden_case(case_name="case-m", workflow_name="beta"))
        cases = store.list()
        names = [(c.workflow_name, c.case_name) for c in cases]
        assert names == [("alpha", "case-a"), ("alpha", "case-z"), ("beta", "case-m")]

    def test_list_raises_on_corrupt_file(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        workflow_dir = tmp_path / "wf"
        workflow_dir.mkdir(parents=True)
        (workflow_dir / "bad.json").write_text("not json", encoding="utf-8")
        with pytest.raises(GoldenCaseRepositoryError, match="Failed to read"):
            store.list()


class TestLocalGoldenCaseStoreDelete:
    def test_delete_existing_returns_true(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        store.save(_make_golden_case())
        assert store.delete("translate", "happy-path") is True

    def test_delete_removes_file(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        case = _make_golden_case()
        path_str = store.save(case)
        store.delete("translate", "happy-path")
        assert not Path(path_str).exists()

    def test_delete_nonexistent_returns_false(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        assert store.delete("translate", "nonexistent") is False

    def test_delete_raises_on_failure(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        store.save(_make_golden_case())
        with patch("pathlib.Path.unlink", side_effect=OSError("Permission denied")):
            with pytest.raises(GoldenCaseRepositoryError, match="Failed to delete"):
                store.delete("translate", "happy-path")


class TestLocalGoldenCaseStoreExists:
    def test_exists_returns_true(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        store.save(_make_golden_case())
        assert store.exists("translate", "happy-path") is True

    def test_exists_returns_false(self, tmp_path: Path) -> None:
        store = LocalGoldenCaseStore(base_dir=tmp_path)
        assert store.exists("translate", "nonexistent") is False
