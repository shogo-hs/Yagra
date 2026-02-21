"""Unit tests for golden test case domain entities and comparison functions (G-20)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from yagra.domain.entities.comparison import (
    ComparisonStrategy,
    compare_exact,
    compare_snapshots,
    compare_structural,
)
from yagra.domain.entities.golden_case import (
    GoldenCase,
    GoldenTestResult,
    NodeComparisonResult,
    NodeSnapshot,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_node_snapshot(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "node_id": "translate",
        "handler": "llm",
        "is_llm_handler": True,
        "input_snapshot": {"text": "hello"},
        "output_snapshot": {"translated": "こんにちは"},
        "comparison_strategy": "auto",
    }
    base.update(overrides)
    return base


def _make_golden_case(**overrides: Any) -> dict[str, Any]:
    now = datetime.now(tz=UTC).isoformat()
    base: dict[str, Any] = {
        "schema_version": "1.0",
        "case_name": "happy-path",
        "description": "Normal translation flow",
        "workflow_name": "translate",
        "workflow_path": "workflows/translate.yaml",
        "created_at": now,
        "source_run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "initial_state": {"text": "hello"},
        "final_state": {"text": "hello", "translated": "こんにちは"},
        "execution_path": ["translate"],
        "node_snapshots": {
            "translate": _make_node_snapshot(),
        },
        "metadata": {},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# ComparisonStrategy enum
# ---------------------------------------------------------------------------


class TestComparisonStrategy:
    def test_enum_values(self) -> None:
        assert ComparisonStrategy.EXACT == "exact"
        assert ComparisonStrategy.STRUCTURAL == "structural"
        assert ComparisonStrategy.SKIP == "skip"
        assert ComparisonStrategy.AUTO == "auto"

    def test_from_string(self) -> None:
        assert ComparisonStrategy("exact") == ComparisonStrategy.EXACT
        assert ComparisonStrategy("structural") == ComparisonStrategy.STRUCTURAL

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            ComparisonStrategy("invalid")


# ---------------------------------------------------------------------------
# compare_exact
# ---------------------------------------------------------------------------


class TestCompareExact:
    def test_identical_dicts_return_none(self) -> None:
        d = {"key": "value", "num": 42}
        assert compare_exact(d, d.copy()) is None

    def test_empty_dicts_return_none(self) -> None:
        assert compare_exact({}, {}) is None

    def test_detects_added_keys(self) -> None:
        diff = compare_exact({"a": 1}, {"a": 1, "b": 2})
        assert diff is not None
        assert diff["added"] == ["b"]

    def test_detects_removed_keys(self) -> None:
        diff = compare_exact({"a": 1, "b": 2}, {"a": 1})
        assert diff is not None
        assert diff["removed"] == ["b"]

    def test_detects_changed_values(self) -> None:
        diff = compare_exact({"a": 1}, {"a": 2})
        assert diff is not None
        assert diff["changed"]["a"] == {"expected": 1, "actual": 2}

    def test_detects_multiple_differences(self) -> None:
        diff = compare_exact(
            {"a": 1, "b": 2, "c": 3},
            {"a": 99, "c": 3, "d": 4},
        )
        assert diff is not None
        assert "b" in diff["removed"]
        assert "d" in diff["added"]
        assert "a" in diff["changed"]


# ---------------------------------------------------------------------------
# compare_structural
# ---------------------------------------------------------------------------


class TestCompareStructural:
    def test_same_keys_and_types_return_none(self) -> None:
        expected = {"a": "hello", "b": 42}
        actual = {"a": "world", "b": 99}
        assert compare_structural(expected, actual) is None

    def test_empty_dicts_return_none(self) -> None:
        assert compare_structural({}, {}) is None

    def test_detects_added_keys(self) -> None:
        diff = compare_structural({"a": 1}, {"a": 1, "b": 2})
        assert diff is not None
        assert diff["added"] == ["b"]

    def test_detects_removed_keys(self) -> None:
        diff = compare_structural({"a": 1, "b": 2}, {"a": 1})
        assert diff is not None
        assert diff["removed"] == ["b"]

    def test_detects_type_mismatch(self) -> None:
        diff = compare_structural({"a": "string"}, {"a": 42})
        assert diff is not None
        assert diff["type_mismatch"]["a"] == {"expected": "str", "actual": "int"}

    def test_ignores_value_differences(self) -> None:
        assert compare_structural({"a": "foo"}, {"a": "bar"}) is None


# ---------------------------------------------------------------------------
# compare_snapshots
# ---------------------------------------------------------------------------


class TestCompareSnapshots:
    def test_skip_strategy_always_returns_none(self) -> None:
        result = compare_snapshots({"a": 1}, {"b": 2}, ComparisonStrategy.SKIP)
        assert result is None

    def test_exact_strategy_delegates(self) -> None:
        result = compare_snapshots({"a": 1}, {"a": 2}, ComparisonStrategy.EXACT)
        assert result is not None
        assert "changed" in result

    def test_structural_strategy_delegates(self) -> None:
        result = compare_snapshots({"a": "hello"}, {"a": 42}, ComparisonStrategy.STRUCTURAL)
        assert result is not None
        assert "type_mismatch" in result

    def test_auto_resolves_to_exact_for_non_llm(self) -> None:
        result = compare_snapshots(
            {"a": 1}, {"a": 2}, ComparisonStrategy.AUTO, is_llm_handler=False
        )
        assert result is not None
        assert "changed" in result

    def test_auto_resolves_to_structural_for_llm(self) -> None:
        # Values differ but types match -> structural passes
        result = compare_snapshots(
            {"a": "hello"}, {"a": "world"}, ComparisonStrategy.AUTO, is_llm_handler=True
        )
        assert result is None

    def test_auto_llm_detects_type_mismatch(self) -> None:
        result = compare_snapshots(
            {"a": "hello"}, {"a": 42}, ComparisonStrategy.AUTO, is_llm_handler=True
        )
        assert result is not None


# ---------------------------------------------------------------------------
# NodeSnapshot
# ---------------------------------------------------------------------------


class TestNodeSnapshot:
    def test_valid_construction(self) -> None:
        snap = NodeSnapshot.model_validate(_make_node_snapshot())
        assert snap.node_id == "translate"
        assert snap.is_llm_handler is True
        assert snap.comparison_strategy == ComparisonStrategy.AUTO

    def test_default_comparison_strategy(self) -> None:
        data = _make_node_snapshot()
        del data["comparison_strategy"]
        snap = NodeSnapshot.model_validate(data)
        assert snap.comparison_strategy == ComparisonStrategy.AUTO

    def test_rejects_extra_fields(self) -> None:
        data = _make_node_snapshot(unknown_field="bad")
        with pytest.raises(ValidationError):
            NodeSnapshot.model_validate(data)

    def test_serialization_roundtrip(self) -> None:
        snap = NodeSnapshot.model_validate(_make_node_snapshot())
        dumped = snap.model_dump(mode="json")
        restored = NodeSnapshot.model_validate(dumped)
        assert restored == snap


# ---------------------------------------------------------------------------
# GoldenCase
# ---------------------------------------------------------------------------


class TestGoldenCase:
    def test_valid_construction(self) -> None:
        case = GoldenCase.model_validate(_make_golden_case())
        assert case.case_name == "happy-path"
        assert case.workflow_name == "translate"
        assert len(case.node_snapshots) == 1

    def test_defaults(self) -> None:
        data = _make_golden_case()
        del data["description"]
        del data["metadata"]
        case = GoldenCase.model_validate(data)
        assert case.description == ""
        assert case.metadata == {}

    def test_rejects_extra_fields(self) -> None:
        data = _make_golden_case(unknown="bad")
        with pytest.raises(ValidationError):
            GoldenCase.model_validate(data)

    def test_serialization_roundtrip(self) -> None:
        case = GoldenCase.model_validate(_make_golden_case())
        dumped = case.model_dump(mode="json")
        restored = GoldenCase.model_validate(dumped)
        assert restored.case_name == case.case_name
        assert restored.workflow_name == case.workflow_name
        assert restored.execution_path == case.execution_path
        assert restored.node_snapshots == case.node_snapshots

    def test_schema_version_default(self) -> None:
        data = _make_golden_case()
        del data["schema_version"]
        case = GoldenCase.model_validate(data)
        assert case.schema_version == "1.0"


# ---------------------------------------------------------------------------
# NodeComparisonResult
# ---------------------------------------------------------------------------


class TestNodeComparisonResult:
    def test_pass_result(self) -> None:
        result = NodeComparisonResult(
            node_id="translate",
            status="pass",
            strategy_used=ComparisonStrategy.EXACT,
            input_match=True,
            output_match=True,
            message="All checks passed",
        )
        assert result.status == "pass"
        assert result.input_diff is None
        assert result.output_diff is None

    def test_fail_result_with_diffs(self) -> None:
        result = NodeComparisonResult(
            node_id="translate",
            status="fail",
            strategy_used=ComparisonStrategy.EXACT,
            input_match=True,
            output_match=False,
            output_diff={"changed": {"key": {"expected": 1, "actual": 2}}},
            message="Output mismatch",
        )
        assert result.status == "fail"
        assert result.output_diff is not None

    def test_missing_status(self) -> None:
        result = NodeComparisonResult(
            node_id="missing_node",
            status="missing",
            strategy_used=ComparisonStrategy.EXACT,
            message="Node was expected but not executed",
        )
        assert result.status == "missing"
        assert result.input_match is None

    def test_unexpected_status(self) -> None:
        result = NodeComparisonResult(
            node_id="extra_node",
            status="unexpected",
            strategy_used=ComparisonStrategy.EXACT,
            message="Node was not expected",
        )
        assert result.status == "unexpected"

    def test_skip_status(self) -> None:
        result = NodeComparisonResult(
            node_id="skipped_node",
            status="skip",
            strategy_used=ComparisonStrategy.SKIP,
            message="Comparison skipped",
        )
        assert result.status == "skip"

    def test_rejects_invalid_status(self) -> None:
        with pytest.raises(ValidationError):
            NodeComparisonResult(
                node_id="node",
                status="invalid",  # type: ignore[arg-type]
                strategy_used=ComparisonStrategy.EXACT,
            )

    def test_serialization_roundtrip(self) -> None:
        result = NodeComparisonResult(
            node_id="translate",
            status="pass",
            strategy_used=ComparisonStrategy.STRUCTURAL,
            input_match=True,
            output_match=True,
        )
        dumped = result.model_dump(mode="json")
        restored = NodeComparisonResult.model_validate(dumped)
        assert restored == result


# ---------------------------------------------------------------------------
# GoldenTestResult
# ---------------------------------------------------------------------------


class TestGoldenTestResult:
    def test_passed_result(self) -> None:
        result = GoldenTestResult(
            case_name="happy-path",
            workflow_name="translate",
            passed=True,
            executed_at=datetime.now(tz=UTC),
            execution_path_match=True,
            expected_path=["translate"],
            actual_path=["translate"],
            node_results=[],
            summary="All tests passed",
        )
        assert result.passed is True

    def test_failed_result(self) -> None:
        result = GoldenTestResult(
            case_name="happy-path",
            workflow_name="translate",
            passed=False,
            executed_at=datetime.now(tz=UTC),
            execution_path_match=False,
            expected_path=["translate", "format"],
            actual_path=["translate"],
            node_results=[],
            summary="Execution path mismatch",
        )
        assert result.passed is False
        assert result.execution_path_match is False

    def test_serialization_roundtrip(self) -> None:
        result = GoldenTestResult(
            case_name="happy-path",
            workflow_name="translate",
            passed=True,
            executed_at=datetime.now(tz=UTC),
            execution_path_match=True,
            expected_path=["a"],
            actual_path=["a"],
            node_results=[
                NodeComparisonResult(
                    node_id="a",
                    status="pass",
                    strategy_used=ComparisonStrategy.EXACT,
                    input_match=True,
                    output_match=True,
                ),
            ],
            summary="OK",
        )
        dumped = result.model_dump(mode="json")
        restored = GoldenTestResult.model_validate(dumped)
        assert restored.case_name == result.case_name
        assert len(restored.node_results) == 1

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            GoldenTestResult(
                case_name="x",
                workflow_name="y",
                passed=True,
                executed_at=datetime.now(tz=UTC),
                execution_path_match=True,
                summary="ok",
                extra_field="bad",  # type: ignore[call-arg]
            )
