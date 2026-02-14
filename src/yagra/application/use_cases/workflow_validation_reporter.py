"""WebUI 向けの workflow 検証レポートを生成する。"""

from __future__ import annotations

from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from yagra.application.services import WorkflowReferenceError, resolve_workflow_references
from yagra.application.use_cases.state_graph_builder import collect_edge_rule_issues
from yagra.domain.entities import GraphSpec
from yagra.domain.services.schema_validator import collect_graph_structure_issues

type Location = tuple[str | int, ...]


@dataclass(frozen=True, slots=True)
class WorkflowValidationIssue:
    """UI 表示向けの単一検証問題。"""

    code: str
    message: str
    location: Location = ()


@dataclass(slots=True)
class WorkflowValidationReport:
    """Workflow 検証結果を保持するレポート。"""

    issues: list[WorkflowValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """問題が存在しないかを返す。"""
        return not self.issues


def validate_workflow_for_ui(
    workflow_path: str | PathLike[str],
    bundle_root: str | PathLike[str] | None = None,
) -> WorkflowValidationReport:
    """Workflow を UI 向けに検証して構造化レポートを返す。

    Args:
        workflow_path: 入口となる workflow YAML のパス。
        bundle_root: 分割参照時の基準ディレクトリ。未指定時は workflow 親を使う。

    Returns:
        検証結果を保持する `WorkflowValidationReport`。
    """
    report = WorkflowValidationReport()
    workflow_abspath = Path(workflow_path).expanduser().resolve()
    bundle_root_path = Path(bundle_root).expanduser().resolve() if bundle_root is not None else None

    payload = _load_yaml_mapping_for_ui(path=workflow_abspath, report=report)
    if payload is None:
        return report

    try:
        resolved_payload = resolve_workflow_references(
            payload=payload,
            workflow_path=workflow_abspath,
            bundle_root=bundle_root_path,
        )
    except WorkflowReferenceError as exc:
        report.issues.append(
            WorkflowValidationIssue(
                code="reference_error",
                message=str(exc),
                location=exc.location,
            )
        )
        return report

    spec = _validate_graph_spec_for_ui(resolved_payload=resolved_payload, report=report)
    if spec is None:
        return report

    for structure_issue in collect_graph_structure_issues(spec):
        report.issues.append(
            WorkflowValidationIssue(
                code="structure_error",
                message=structure_issue.message,
                location=structure_issue.location,
            )
        )

    for edge_rule_issue in collect_edge_rule_issues(spec):
        report.issues.append(
            WorkflowValidationIssue(
                code="edge_rule_error",
                message=edge_rule_issue.message,
                location=edge_rule_issue.location,
            )
        )

    return report


def _load_yaml_mapping_for_ui(
    path: Path, report: WorkflowValidationReport
) -> dict[str, Any] | None:
    """YAML ファイルを辞書として読み込み、失敗時は report に記録する。

    Args:
        path: 読み込み対象の workflow パス。
        report: 問題を追加する検証レポート。

    Returns:
        読み込んだ辞書データ。読み込み失敗時は `None`。
    """
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        report.issues.append(
            WorkflowValidationIssue(
                code="schema_error",
                message=f"workflow の読み込みに失敗しました: {exc}",
                location=(),
            )
        )
        return None

    if not isinstance(payload, dict):
        report.issues.append(
            WorkflowValidationIssue(
                code="schema_error",
                message=f"workflow must be a mapping: {path}",
                location=(),
            )
        )
        return None

    return payload


def _validate_graph_spec_for_ui(
    resolved_payload: dict[str, Any],
    report: WorkflowValidationReport,
) -> GraphSpec | None:
    """解決済み payload を GraphSpec として検証する。

    Args:
        resolved_payload: 参照解決済みの workflow データ。
        report: 問題を追加する検証レポート。

    Returns:
        検証済み `GraphSpec`。スキーマエラー時は `None`。
    """
    try:
        return GraphSpec.model_validate(resolved_payload)
    except ValidationError as exc:
        issues = _convert_pydantic_errors(exc)
        if not issues:
            issues = [
                WorkflowValidationIssue(
                    code="schema_error",
                    message="Pydanticスキーマ検証に失敗しました",
                    location=(),
                )
            ]
        report.issues.extend(issues)
        return None


def _convert_pydantic_errors(exc: ValidationError) -> list[WorkflowValidationIssue]:
    """Pydantic ValidationError を UI 向け issue へ変換する。

    Args:
        exc: 変換対象の Pydantic 検証エラー。

    Returns:
        変換後の issue 一覧。
    """
    issues: list[WorkflowValidationIssue] = []
    for error in exc.errors():
        raw_loc = error.get("loc", ())
        message = str(error.get("msg", "validation error"))
        issues.append(
            WorkflowValidationIssue(
                code="schema_error",
                message=message,
                location=_normalize_location(raw_loc),
            )
        )
    return issues


def _normalize_location(raw_loc: Any) -> Location:
    """Pydantic の loc 値を `Location` 形式へ正規化する。

    Args:
        raw_loc: Pydantic が返す location 値。

    Returns:
        正規化済み location タプル。
    """
    if not isinstance(raw_loc, tuple):
        return ()

    normalized: list[str | int] = []
    for part in raw_loc:
        if isinstance(part, (str, int)):
            normalized.append(part)
        else:
            normalized.append(str(part))
    return tuple(normalized)
