"""Unit tests for LocalTraceSink (G-14)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from yagra.adapters.outbound.local_trace_sink import LocalTraceSink
from yagra.domain.entities.trace import NodeStatus, RunSummary, WorkflowRunTrace


def _make_minimal_trace(workflow_name: str = "test") -> WorkflowRunTrace:
    now = datetime.now(tz=UTC)
    summary = RunSummary(
        total_nodes_executed=0,
        succeeded_nodes=0,
        failed_nodes=0,
        total_duration_ms=100.0,
    )
    return WorkflowRunTrace(
        workflow_name=workflow_name,
        workflow_version="1.0",
        started_at=now,
        ended_at=now,
        status=NodeStatus.SUCCESS,
        nodes=[],
        summary=summary,
    )


class TestLocalTraceSink:
    def test_write_creates_file(self, tmp_path: Path) -> None:
        sink = LocalTraceSink(base_dir=tmp_path)
        trace = _make_minimal_trace("translate")
        path_str = sink.write(trace)
        assert Path(path_str).exists()

    def test_write_creates_workflow_subdirectory(self, tmp_path: Path) -> None:
        sink = LocalTraceSink(base_dir=tmp_path)
        trace = _make_minimal_trace("my_workflow")
        sink.write(trace)
        assert (tmp_path / "my_workflow").is_dir()

    def test_filename_pattern(self, tmp_path: Path) -> None:
        sink = LocalTraceSink(base_dir=tmp_path)
        trace = _make_minimal_trace("translate")
        path_str = sink.write(trace)
        filename = Path(path_str).name
        # e.g. translate_20260220T143022_a1b2c3d4.json
        assert filename.startswith("translate_")
        assert filename.endswith(".json")
        parts = filename[len("translate_") : -len(".json")].split("_")
        assert len(parts) == 2  # timestamp + run_id_short

    def test_write_returns_absolute_path(self, tmp_path: Path) -> None:
        sink = LocalTraceSink(base_dir=tmp_path)
        trace = _make_minimal_trace()
        path_str = sink.write(trace)
        assert Path(path_str).is_absolute()

    def test_written_json_is_valid(self, tmp_path: Path) -> None:
        sink = LocalTraceSink(base_dir=tmp_path)
        trace = _make_minimal_trace("my_flow")
        path_str = sink.write(trace)
        content = json.loads(Path(path_str).read_text(encoding="utf-8"))
        assert content["schema_version"] == "1.0"
        assert content["workflow_name"] == "my_flow"
        assert content["status"] == "success"
        assert isinstance(content["run_id"], str)

    def test_compact_mode(self, tmp_path: Path) -> None:
        sink = LocalTraceSink(base_dir=tmp_path, indent=None)
        trace = _make_minimal_trace()
        path_str = sink.write(trace)
        content = Path(path_str).read_text(encoding="utf-8")
        # compact: no indentation
        assert "\n  " not in content

    def test_flush_is_noop(self, tmp_path: Path) -> None:
        sink = LocalTraceSink(base_dir=tmp_path)
        sink.flush()  # Should not raise

    def test_multiple_writes_produce_separate_files(self, tmp_path: Path) -> None:
        sink = LocalTraceSink(base_dir=tmp_path)
        trace1 = _make_minimal_trace("flow")
        trace2 = _make_minimal_trace("flow")
        path1 = sink.write(trace1)
        import time

        time.sleep(0.001)  # ensure different timestamps
        path2 = sink.write(trace2)
        # Different run_ids -> different filenames (at minimum the id part differs)
        assert path1 != path2
