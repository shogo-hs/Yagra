"""E2E integration test for the optimization cycle: Build -> Run & Observe -> Analyze & Propose -> Approve & Update.

This test verifies that the full four-phase optimization cycle works end-to-end
without relying on any external LLM API calls.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import yaml

from yagra import Yagra
from yagra.adapters.inbound.mcp_server import (
    _tool_analyze_traces,
    _tool_apply_update,
    _tool_get_traces,
    _tool_propose_update,
    _tool_rollback_update,
)
from yagra.application.use_cases.trace_aggregator import aggregate_traces, load_traces

# ---------------------------------------------------------------------------
# Test workflow YAML and helper
# ---------------------------------------------------------------------------

_WORKFLOW_YAML_V1 = """\
version: "1"
start_at: greet
end_at:
  - greet
nodes:
  - id: greet
    handler: greet_handler
edges: []
"""

_WORKFLOW_YAML_V2 = """\
version: "1"
start_at: greet
end_at:
  - farewell
nodes:
  - id: greet
    handler: greet_handler
  - id: farewell
    handler: farewell_handler
edges:
  - source: greet
    target: farewell
"""


def _greet_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Simple custom handler that returns a greeting message."""
    return {"message": "hello"}


def _farewell_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Simple custom handler that appends a farewell to state."""
    return {"farewell": "goodbye"}


class TestOptimizationCycleE2E:
    """E2E tests verifying the full optimization cycle.

    Covers the four-phase lifecycle:
      Phase 1: Build  (workflow YAML definition and validation)
      Phase 2: Run & Observe  (execution with trace output)
      Phase 3: Analyze & Propose  (trace analysis and candidate YAML diff)
      Phase 4: Approve & Update  (apply and rollback)
    """

    def test_full_optimization_cycle(self, tmp_path: Path) -> None:
        """Build -> Run & Observe -> Analyze & Propose -> Approve & Update.

        全工程が正常に動作することを検証する。
        """
        # ---------------------------------------------------------------
        # Phase 1: Build - ワークフロー定義と検証
        # ---------------------------------------------------------------

        workflow_path = tmp_path / "workflow.yaml"
        workflow_path.write_text(_WORKFLOW_YAML_V1, encoding="utf-8")

        # MCP validate_workflow でバリデーション
        from yagra.adapters.inbound.mcp_server import _tool_validate_workflow

        validation_result = _tool_validate_workflow(
            yaml_content=_WORKFLOW_YAML_V1,
            base_dir=str(tmp_path),
        )
        assert validation_result["is_valid"] is True, (
            f"Phase 1: workflow validation failed: {validation_result.get('issues')}"
        )

        # ---------------------------------------------------------------
        # Phase 2: Run & Observe - 実行とトレース収集
        # ---------------------------------------------------------------

        trace_dir = tmp_path / ".yagra" / "traces"
        registry = {"greet_handler": _greet_handler}

        yagra = Yagra.from_workflow(
            workflow_path=workflow_path,
            registry=registry,
            observability=True,
        )

        # trace=True でトレースをtmp_path配下に書き出す
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = yagra.invoke(
                state={},
                trace=True,
                trace_dir=trace_dir,
            )

        # ワークフロー実行結果の確認
        assert result.get("message") == "hello", f"Phase 2: unexpected workflow result: {result}"

        # .yagra/traces/ 配下にトレースファイルが出力されていることを確認
        trace_files = list(trace_dir.glob("**/*.json"))
        assert len(trace_files) >= 1, (
            f"Phase 2: expected at least 1 trace file in {trace_dir}, found none"
        )

        # ---------------------------------------------------------------
        # Phase 3: Analyze & Propose - トレース分析と変更提案
        # ---------------------------------------------------------------

        # load_traces + aggregate_traces でサマリを生成
        traces = load_traces(trace_dir=str(trace_dir))
        assert len(traces) >= 1, f"Phase 3: load_traces returned no traces from {trace_dir}"

        summary = aggregate_traces(traces)
        assert summary.total_runs >= 1
        assert summary.workflow_name == "workflow"
        assert summary.successful_runs >= 1

        # MCP _tool_get_traces でトレース取得できることを確認
        get_traces_result = _tool_get_traces(
            trace_dir=str(trace_dir),
            workflow_name="workflow",
            limit=20,
        )
        assert "error" not in get_traces_result, (
            f"Phase 3: _tool_get_traces returned error: {get_traces_result.get('error')}"
        )
        assert get_traces_result["count"] >= 1
        assert len(get_traces_result["traces"]) >= 1

        # MCP _tool_analyze_traces でサマリ取得できることを確認
        analyze_result = _tool_analyze_traces(
            trace_dir=str(trace_dir),
            workflow_name="workflow",
        )
        assert "error" not in analyze_result, (
            f"Phase 3: _tool_analyze_traces returned error: {analyze_result.get('error')}"
        )
        assert analyze_result["total_runs"] >= 1
        assert analyze_result["workflow_name"] == "workflow"
        assert len(analyze_result["node_stats"]) >= 1
        # greet ノードの統計が含まれていることを確認
        node_ids = [ns["node_id"] for ns in analyze_result["node_stats"]]
        assert "greet" in node_ids, f"Phase 3: expected 'greet' node in node_stats, got: {node_ids}"

        # MCP _tool_propose_update で候補 YAML の diff とバリデーション結果が返ることを確認
        propose_result = _tool_propose_update(
            workflow_path=str(workflow_path),
            candidate_yaml=_WORKFLOW_YAML_V2,
            reason="add farewell node to complete the greeting cycle",
        )
        assert "error" not in propose_result, (
            f"Phase 3: _tool_propose_update returned error: {propose_result.get('error')}"
        )
        assert propose_result["is_valid"] is True, (
            f"Phase 3: candidate YAML validation failed: {propose_result.get('issues')}"
        )
        assert propose_result["diff"] != "", "Phase 3: expected a non-empty diff between v1 and v2"
        assert propose_result["reason"] == "add farewell node to complete the greeting cycle"

        # ---------------------------------------------------------------
        # Phase 4: Approve & Update - YAML 適用とロールバック
        # ---------------------------------------------------------------

        backup_dir = tmp_path / ".yagra" / "backups"

        # MCP _tool_apply_update で YAML を適用（バックアップ付き）
        # NOTE: この E2E では golden case を意図的に作成していないため、新デフォルト
        # golden_pass_required=True でも total=0 として扱われ、warnings 付きで apply
        # が許可されることを確認する（silent success 防止の契約）。
        golden_dir = tmp_path / ".yagra" / "golden"
        apply_result = _tool_apply_update(
            workflow_path=str(workflow_path),
            candidate_yaml=_WORKFLOW_YAML_V2,
            backup_dir=str(backup_dir),
            golden_dir=str(golden_dir),
        )
        assert "error" not in apply_result, (
            f"Phase 4: _tool_apply_update returned error: {apply_result.get('error')}"
        )
        assert apply_result.get("success") is True, (
            f"Phase 4: apply_update did not return success=True: {apply_result}"
        )
        # golden case 未定義 → warnings=['no_golden_cases_defined'] が返ることを明示
        assert apply_result.get("warnings") == ["no_golden_cases_defined"], (
            "Phase 4: expected warnings=['no_golden_cases_defined'] when no golden cases are "
            f"defined, got: {apply_result.get('warnings')!r}"
        )

        # バックアップ ID が返ることを確認
        backup_id = apply_result.get("backup_id")
        assert backup_id is not None and backup_id != "", (
            f"Phase 4: expected a non-empty backup_id, got: {backup_id!r}"
        )

        # YAML が v2 に更新されていることを確認
        applied_content = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        assert isinstance(applied_content, dict)
        node_ids_applied = [n["id"] for n in applied_content.get("nodes", [])]
        assert "farewell" in node_ids_applied, (
            f"Phase 4: expected 'farewell' node after apply, got nodes: {node_ids_applied}"
        )

        # MCP _tool_rollback_update でロールバックできることを確認
        rollback_result = _tool_rollback_update(
            workflow_path=str(workflow_path),
            backup_id=backup_id,
            backup_dir=str(backup_dir),
        )
        assert "error" not in rollback_result, (
            f"Phase 4: _tool_rollback_update returned error: {rollback_result.get('error')}"
        )
        assert rollback_result.get("success") is True, (
            f"Phase 4: rollback did not return success=True: {rollback_result}"
        )

        # ロールバック後に元の内容（v1）に戻ることを確認
        rolled_back_content = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        assert isinstance(rolled_back_content, dict)
        node_ids_rolled_back = [n["id"] for n in rolled_back_content.get("nodes", [])]
        assert "farewell" not in node_ids_rolled_back, (
            f"Phase 4: 'farewell' node should not be present after rollback, "
            f"got nodes: {node_ids_rolled_back}"
        )
        assert "greet" in node_ids_rolled_back, (
            f"Phase 4: 'greet' node should be present after rollback, "
            f"got nodes: {node_ids_rolled_back}"
        )
