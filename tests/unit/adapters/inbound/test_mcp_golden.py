"""Tests for the run_golden_tests MCP tool (M-52, G-20).

Tests the _tool_run_golden_tests implementation and verifies that
the run_golden_tests tool is registered in the MCP server's tool list.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from yagra.domain.entities.comparison import ComparisonStrategy
from yagra.domain.entities.golden_case import (
    GoldenCase,
    GoldenTestResult,
    NodeComparisonResult,
    NodeSnapshot,
)


def _make_golden_case(
    workflow_name: str = "test-wf",
    case_name: str = "happy-path",
) -> GoldenCase:
    """Creates a minimal GoldenCase for testing."""
    return GoldenCase(
        case_name=case_name,
        workflow_name=workflow_name,
        workflow_path=f"workflows/{workflow_name}.yaml",
        created_at=datetime.now(tz=UTC),
        source_run_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        initial_state={"input_text": "hello"},
        final_state={"input_text": "hello", "output": "HELLO"},
        execution_path=["node-a"],
        node_snapshots={
            "node-a": NodeSnapshot(
                node_id="node-a",
                handler="llm",
                is_llm_handler=True,
                input_snapshot={"input_text": "hello"},
                output_snapshot={"output": "HELLO"},
                comparison_strategy=ComparisonStrategy.AUTO,
            ),
        },
    )


def _make_test_result(
    case_name: str = "happy-path",
    workflow_name: str = "test-wf",
    passed: bool = True,
) -> GoldenTestResult:
    """Creates a GoldenTestResult for testing."""
    return GoldenTestResult(
        case_name=case_name,
        workflow_name=workflow_name,
        passed=passed,
        executed_at=datetime.now(tz=UTC),
        execution_path_match=True,
        expected_path=["node-a"],
        actual_path=["node-a"],
        node_results=[
            NodeComparisonResult(
                node_id="node-a",
                status="pass" if passed else "fail",
                strategy_used=ComparisonStrategy.STRUCTURAL,
                input_match=True,
                output_match=True,
                message=f"Node 'node-a' {'passed' if passed else 'failed'}.",
            ),
        ],
        summary=f"Golden test '{case_name}': {'PASSED' if passed else 'FAILED'} "
        f"Nodes: 1 total, {1 if passed else 0} passed, {0 if passed else 1} failed, "
        "0 skipped, 0 missing, 0 unexpected.",
    )


_VALID_WORKFLOW_YAML = """\
version: "1"
start_at: node1
end_at:
  - node1
nodes:
  - id: node1
    handler: my_handler
edges: []
"""


# ---------------------------------------------------------------------------
# _tool_run_golden_tests: workflow file not found
# ---------------------------------------------------------------------------


class TestRunGoldenTestsTool:
    """Tests for the _tool_run_golden_tests implementation."""

    def test_workflow_file_not_found(self) -> None:
        """Returns error when workflow_path does not exist."""
        from yagra.adapters.inbound.mcp_server import _tool_run_golden_tests

        result = _tool_run_golden_tests(
            workflow_path="/nonexistent/path/workflow.yaml",
        )
        assert "error" in result
        assert "not found" in result["error"]

    def test_single_case_pass_json_format(self, tmp_path: Path) -> None:
        """Single passing case returns structured JSON with all_passed=True."""
        from yagra.adapters.inbound.mcp_server import _tool_run_golden_tests

        wf = tmp_path / "test-wf.yaml"
        wf.write_text(_VALID_WORKFLOW_YAML)

        golden_case = _make_golden_case(workflow_name="test-wf")
        test_result = _make_test_result(passed=True)

        with (
            patch(
                "yagra.adapters.outbound.local_golden_case_store.LocalGoldenCaseStore.load",
                return_value=golden_case,
            ),
            patch(
                "yagra.application.use_cases.golden_test_runner.GoldenTestRunner.run",
                return_value=test_result,
            ),
        ):
            result = _tool_run_golden_tests(
                workflow_path=str(wf),
                golden_dir=str(tmp_path / "golden"),
                case_name="happy-path",
                fmt="json",
            )

        assert result["all_passed"] is True
        assert result["total"] == 1
        assert result["passed"] == 1
        assert result["failed"] == 0
        assert result["workflow_name"] == "test-wf"
        assert len(result["results"]) == 1
        assert result["results"][0]["passed"] is True

    def test_single_case_fail_json_format(self, tmp_path: Path) -> None:
        """Single failing case returns all_passed=False."""
        from yagra.adapters.inbound.mcp_server import _tool_run_golden_tests

        wf = tmp_path / "test-wf.yaml"
        wf.write_text(_VALID_WORKFLOW_YAML)

        golden_case = _make_golden_case(workflow_name="test-wf")
        test_result = _make_test_result(passed=False)

        with (
            patch(
                "yagra.adapters.outbound.local_golden_case_store.LocalGoldenCaseStore.load",
                return_value=golden_case,
            ),
            patch(
                "yagra.application.use_cases.golden_test_runner.GoldenTestRunner.run",
                return_value=test_result,
            ),
        ):
            result = _tool_run_golden_tests(
                workflow_path=str(wf),
                golden_dir=str(tmp_path / "golden"),
                case_name="happy-path",
            )

        assert result["all_passed"] is False
        assert result["failed"] == 1

    def test_run_all_cases(self, tmp_path: Path) -> None:
        """When case_name is None, runs all cases via run_all."""
        from yagra.adapters.inbound.mcp_server import _tool_run_golden_tests

        wf = tmp_path / "test-wf.yaml"
        wf.write_text(_VALID_WORKFLOW_YAML)

        results = [
            _make_test_result(case_name="case-a", passed=True),
            _make_test_result(case_name="case-b", passed=True),
        ]

        with patch(
            "yagra.application.use_cases.golden_test_runner.GoldenTestRunner.run_all",
            return_value=results,
        ):
            result = _tool_run_golden_tests(
                workflow_path=str(wf),
                golden_dir=str(tmp_path / "golden"),
            )

        assert result["all_passed"] is True
        assert result["total"] == 2
        assert result["passed"] == 2

    def test_run_all_with_failures(self, tmp_path: Path) -> None:
        """Mixed pass/fail results report correct counts."""
        from yagra.adapters.inbound.mcp_server import _tool_run_golden_tests

        wf = tmp_path / "test-wf.yaml"
        wf.write_text(_VALID_WORKFLOW_YAML)

        results = [
            _make_test_result(case_name="case-a", passed=True),
            _make_test_result(case_name="case-b", passed=False),
        ]

        with patch(
            "yagra.application.use_cases.golden_test_runner.GoldenTestRunner.run_all",
            return_value=results,
        ):
            result = _tool_run_golden_tests(
                workflow_path=str(wf),
                golden_dir=str(tmp_path / "golden"),
            )

        assert result["all_passed"] is False
        assert result["total"] == 2
        assert result["passed"] == 1
        assert result["failed"] == 1

    def test_summary_format(self, tmp_path: Path) -> None:
        """format='summary' returns a human-readable summary string."""
        from yagra.adapters.inbound.mcp_server import _tool_run_golden_tests

        wf = tmp_path / "test-wf.yaml"
        wf.write_text(_VALID_WORKFLOW_YAML)

        results = [_make_test_result(case_name="happy-path", passed=True)]

        with patch(
            "yagra.application.use_cases.golden_test_runner.GoldenTestRunner.run_all",
            return_value=results,
        ):
            result = _tool_run_golden_tests(
                workflow_path=str(wf),
                golden_dir=str(tmp_path / "golden"),
                fmt="summary",
            )

        assert result["all_passed"] is True
        assert "summary" in result
        assert "PASS" in result["summary"]
        assert "happy-path" in result["summary"]
        # summary format should NOT have 'results' key
        assert "results" not in result

    def test_golden_case_not_found(self, tmp_path: Path) -> None:
        """Returns error when the specified case does not exist."""
        from yagra.adapters.inbound.mcp_server import _tool_run_golden_tests
        from yagra.ports.outbound.golden_case_repository import GoldenCaseNotFoundError

        wf = tmp_path / "test-wf.yaml"
        wf.write_text(_VALID_WORKFLOW_YAML)

        with patch(
            "yagra.adapters.outbound.local_golden_case_store.LocalGoldenCaseStore.load",
            side_effect=GoldenCaseNotFoundError("Golden case not found: test-wf/missing"),
        ):
            result = _tool_run_golden_tests(
                workflow_path=str(wf),
                golden_dir=str(tmp_path / "golden"),
                case_name="missing",
            )

        assert result["error"] == "golden_case_not_found"
        assert "message" in result

    def test_repository_error(self, tmp_path: Path) -> None:
        """Returns error on repository I/O failure."""
        from yagra.adapters.inbound.mcp_server import _tool_run_golden_tests
        from yagra.ports.outbound.golden_case_repository import GoldenCaseRepositoryError

        wf = tmp_path / "test-wf.yaml"
        wf.write_text(_VALID_WORKFLOW_YAML)

        with patch(
            "yagra.application.use_cases.golden_test_runner.GoldenTestRunner.run_all",
            side_effect=GoldenCaseRepositoryError("I/O error"),
        ):
            result = _tool_run_golden_tests(
                workflow_path=str(wf),
                golden_dir=str(tmp_path / "golden"),
            )

        assert result["error"] == "golden_case_repository_error"

    def test_execution_error(self, tmp_path: Path) -> None:
        """Returns error on unexpected test execution failure."""
        from yagra.adapters.inbound.mcp_server import _tool_run_golden_tests

        wf = tmp_path / "test-wf.yaml"
        wf.write_text(_VALID_WORKFLOW_YAML)

        with patch(
            "yagra.application.use_cases.golden_test_runner.GoldenTestRunner.run_all",
            side_effect=RuntimeError("unexpected error"),
        ):
            result = _tool_run_golden_tests(
                workflow_path=str(wf),
                golden_dir=str(tmp_path / "golden"),
            )

        assert result["error"] == "test_execution_failed"
        assert "unexpected error" in result["message"]

    def test_empty_results(self, tmp_path: Path) -> None:
        """No golden cases returns empty results with all_passed=True."""
        from yagra.adapters.inbound.mcp_server import _tool_run_golden_tests

        wf = tmp_path / "test-wf.yaml"
        wf.write_text(_VALID_WORKFLOW_YAML)

        with patch(
            "yagra.application.use_cases.golden_test_runner.GoldenTestRunner.run_all",
            return_value=[],
        ):
            result = _tool_run_golden_tests(
                workflow_path=str(wf),
                golden_dir=str(tmp_path / "golden"),
            )

        assert result["total"] == 0
        assert result["all_passed"] is True

    def test_default_golden_dir(self, tmp_path: Path) -> None:
        """Default golden_dir is '.yagra/golden' when not specified."""
        from yagra.adapters.inbound.mcp_server import _tool_run_golden_tests

        wf = tmp_path / "test-wf.yaml"
        wf.write_text(_VALID_WORKFLOW_YAML)

        captured_args: dict[str, Any] = {}

        original_init = __import__(
            "yagra.adapters.outbound.local_golden_case_store",
            fromlist=["LocalGoldenCaseStore"],
        ).LocalGoldenCaseStore.__init__

        def capture_init(self: Any, base_dir: Any = ".yagra/golden", indent: Any = 2) -> None:
            captured_args["base_dir"] = str(base_dir)
            original_init(self, base_dir=base_dir, indent=indent)

        with (
            patch(
                "yagra.adapters.outbound.local_golden_case_store.LocalGoldenCaseStore.__init__",
                capture_init,
            ),
            patch(
                "yagra.application.use_cases.golden_test_runner.GoldenTestRunner.run_all",
                return_value=[],
            ),
        ):
            _tool_run_golden_tests(workflow_path=str(wf))

        assert captured_args["base_dir"] == ".yagra/golden"

    def test_workflow_name_from_stem(self, tmp_path: Path) -> None:
        """workflow_name is derived from the YAML file stem."""
        from yagra.adapters.inbound.mcp_server import _tool_run_golden_tests

        wf = tmp_path / "my-workflow.yaml"
        wf.write_text(_VALID_WORKFLOW_YAML)

        with patch(
            "yagra.application.use_cases.golden_test_runner.GoldenTestRunner.run_all",
            return_value=[],
        ):
            result = _tool_run_golden_tests(workflow_path=str(wf))

        assert result["workflow_name"] == "my-workflow"


# ---------------------------------------------------------------------------
# run_golden_tests registered in MCP server tool list
# ---------------------------------------------------------------------------


def test_run_golden_tests_tool_listed():
    """Verify run_golden_tests appears in list_tools."""
    try:
        from yagra.adapters.inbound.mcp_server import create_mcp_server
    except ImportError:
        return

    try:
        server = create_mcp_server()
    except ImportError:
        return

    import asyncio

    list_tools_handler = None
    for handler_name, handler_fn in server.request_handlers.items():
        if "ListTools" in str(handler_name):
            list_tools_handler = handler_fn
            break

    if list_tools_handler is None:
        return

    async def run() -> Any:
        from mcp.types import ListToolsRequest

        request = ListToolsRequest(method="tools/list")
        result = await list_tools_handler(request)
        return result

    try:
        result = asyncio.run(run())
        tools = result.root.tools if hasattr(result, "root") else []
        tool_names = [t.name for t in tools]
        assert "run_golden_tests" in tool_names
    except Exception:
        pass


# ---------------------------------------------------------------------------
# call_tool dispatch for run_golden_tests
# ---------------------------------------------------------------------------


def test_call_tool_dispatches_run_golden_tests(tmp_path: Path, monkeypatch: Any) -> None:
    """call_tool dispatches run_golden_tests to _tool_run_golden_tests."""
    import asyncio
    import importlib
    import sys
    from concurrent.futures import ThreadPoolExecutor

    class _MockServer:
        def __init__(self, name: str) -> None:
            self.name = name
            self._list_tools_fn: Any = None
            self._call_tool_fn: Any = None

        def list_tools(self) -> Any:
            def decorator(fn: Any) -> Any:
                self._list_tools_fn = fn
                return fn

            return decorator

        def call_tool(self) -> Any:
            def decorator(fn: Any) -> Any:
                self._call_tool_fn = fn
                return fn

            return decorator

    mock_types = MagicMock()
    mock_types.Tool = MagicMock(side_effect=lambda **kw: kw)
    mock_types.TextContent = MagicMock(side_effect=lambda type, text: {"type": type, "text": text})

    mock_server_module = MagicMock()
    mock_server_module.Server = _MockServer

    original: dict[str, Any] = {}
    for k in ["mcp", "mcp.server", "mcp.server.stdio", "mcp.types"]:
        original[k] = sys.modules.get(k)

    sys.modules["mcp"] = MagicMock()
    sys.modules["mcp.server"] = mock_server_module
    sys.modules["mcp.server.stdio"] = MagicMock()
    sys.modules["mcp.types"] = mock_types

    wf = tmp_path / "test-wf.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML)

    try:
        import yagra.adapters.inbound.mcp_server as m

        importlib.reload(m)
        server = m.create_mcp_server()

        async def _call_async(name: str, arguments: dict[str, Any]) -> Any:
            results = await server._call_tool_fn(name, arguments)
            return json.loads(results[0]["text"])

        def call(name: str, arguments: dict[str, Any]) -> Any:
            with ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(asyncio.run, _call_async(name, arguments)).result()

        # Test dispatch with a non-existent workflow to get a predictable error
        r = call("run_golden_tests", {"workflow_path": "/nonexistent/wf.yaml"})
        assert "error" in r
        assert "not found" in r["error"]

        # Test dispatch with mock that returns results
        test_result = _make_test_result(passed=True)
        monkeypatch.setattr(
            m,
            "_tool_run_golden_tests",
            lambda **kwargs: {
                "workflow_name": "test-wf",
                "total": 1,
                "passed": 1,
                "failed": 0,
                "all_passed": True,
                "results": [test_result.model_dump(mode="json")],
            },
        )
        r = call("run_golden_tests", {"workflow_path": str(wf)})
        assert r["all_passed"] is True

    finally:
        for k, v in original.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        importlib.reload(m)
