"""Comparison strategy definitions for golden test case evaluation (G-20)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ComparisonStrategy(StrEnum):
    """Strategy for comparing node snapshots during golden test replay.

    Each strategy defines how strictly a node's input/output is compared
    against the golden reference.

    Attributes:
        EXACT: Both keys and values must match exactly.
        STRUCTURAL: Keys and value types must match; values are ignored.
        SKIP: Comparison is skipped entirely for the node.
        AUTO: Resolved at comparison time. LLM nodes use STRUCTURAL,
            non-LLM nodes use EXACT.
    """

    EXACT = "exact"
    STRUCTURAL = "structural"
    SKIP = "skip"
    AUTO = "auto"


def compare_exact(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any] | None:
    """Compare two snapshot dicts for exact equality.

    Args:
        expected: The golden reference snapshot.
        actual: The replayed snapshot to compare.

    Returns:
        None if snapshots match exactly, otherwise a dict describing
        the differences with 'added', 'removed', and 'changed' keys.
    """
    if expected == actual:
        return None

    diff: dict[str, Any] = {}
    added = set(actual.keys()) - set(expected.keys())
    removed = set(expected.keys()) - set(actual.keys())
    changed: dict[str, dict[str, Any]] = {}

    for key in set(expected.keys()) & set(actual.keys()):
        if expected[key] != actual[key]:
            changed[key] = {"expected": expected[key], "actual": actual[key]}

    if added:
        diff["added"] = sorted(added)
    if removed:
        diff["removed"] = sorted(removed)
    if changed:
        diff["changed"] = changed

    return diff if diff else None


def compare_structural(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any] | None:
    """Compare two snapshot dicts for structural compatibility.

    Checks that the same keys exist and that value types match.
    Actual values are not compared.

    Args:
        expected: The golden reference snapshot.
        actual: The replayed snapshot to compare.

    Returns:
        None if snapshots are structurally compatible, otherwise a dict
        describing the differences with 'added', 'removed', and
        'type_mismatch' keys.
    """
    diff: dict[str, Any] = {}
    added = set(actual.keys()) - set(expected.keys())
    removed = set(expected.keys()) - set(actual.keys())
    type_mismatch: dict[str, dict[str, str]] = {}

    for key in set(expected.keys()) & set(actual.keys()):
        expected_type = type(expected[key]).__name__
        actual_type = type(actual[key]).__name__
        if expected_type != actual_type:
            type_mismatch[key] = {"expected": expected_type, "actual": actual_type}

    if added:
        diff["added"] = sorted(added)
    if removed:
        diff["removed"] = sorted(removed)
    if type_mismatch:
        diff["type_mismatch"] = type_mismatch

    return diff if diff else None


def compare_snapshots(
    expected: dict[str, Any],
    actual: dict[str, Any],
    strategy: ComparisonStrategy,
    is_llm_handler: bool = False,
) -> dict[str, Any] | None:
    """Compare two snapshots using the specified strategy.

    When strategy is AUTO, resolves to STRUCTURAL for LLM handlers
    and EXACT for non-LLM handlers.

    Args:
        expected: The golden reference snapshot.
        actual: The replayed snapshot to compare.
        strategy: The comparison strategy to apply.
        is_llm_handler: Whether the node uses an LLM handler.
            Only relevant when strategy is AUTO.

    Returns:
        None if snapshots match according to the strategy, otherwise
        a dict describing the differences.

    Raises:
        ValueError: If strategy is not a valid ComparisonStrategy.
    """
    if strategy == ComparisonStrategy.SKIP:
        return None

    resolved = strategy
    if strategy == ComparisonStrategy.AUTO:
        resolved = ComparisonStrategy.STRUCTURAL if is_llm_handler else ComparisonStrategy.EXACT

    if resolved == ComparisonStrategy.EXACT:
        return compare_exact(expected, actual)
    if resolved == ComparisonStrategy.STRUCTURAL:
        return compare_structural(expected, actual)

    msg = f"Unknown comparison strategy: {strategy}"
    raise ValueError(msg)
