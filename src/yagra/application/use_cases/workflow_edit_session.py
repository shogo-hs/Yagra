"""Workflow 編集セッションの読み込みと差分生成を提供する。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from difflib import unified_diff
from hashlib import sha256
from os import PathLike
from pathlib import Path
from typing import Any, Literal

import yaml

from yagra.application.use_cases.workflow_validation_reporter import (
    WorkflowValidationReport,
    validate_workflow_payload_for_ui,
)

type Location = tuple[str | int, ...]

UI_STATE_SUFFIX = ".workflow-ui.json"


@dataclass(frozen=True, slots=True)
class WorkflowEditSession:
    """編集セッションの現在状態を保持する。"""

    workflow: dict[str, Any]
    ui_state: dict[str, Any]
    revision: str
    validation_report: WorkflowValidationReport


@dataclass(frozen=True, slots=True)
class WorkflowChange:
    """単一変更イベントを表す。"""

    kind: Literal["add", "remove", "update"]
    path: Location
    before: Any | None
    after: Any | None

    def to_dict(self) -> dict[str, Any]:
        """API 応答形式の辞書へ変換する。

        Returns:
            kind, path, before, after を含む辞書。
        """
        return {
            "kind": self.kind,
            "path": list(self.path),
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True, slots=True)
class WorkflowDiffResult:
    """差分計算結果を表す。"""

    base_revision: str
    candidate_revision: str
    summary: dict[str, int]
    changes: tuple[WorkflowChange, ...]
    yaml_unified_diff: str
    validation_report: WorkflowValidationReport

    def to_dict(self) -> dict[str, Any]:
        """API 応答形式の辞書へ変換する。

        Returns:
            差分情報と検証レポートを含む辞書。
        """
        return {
            "base_revision": self.base_revision,
            "candidate_revision": self.candidate_revision,
            "summary": self.summary,
            "changes": [change.to_dict() for change in self.changes],
            "yaml_unified_diff": self.yaml_unified_diff,
            "validation_report": self.validation_report.to_dict(),
        }


def resolve_ui_state_path(
    workflow_path: str | PathLike[str],
    ui_state_path: str | PathLike[str] | None = None,
) -> Path:
    """Workflow に紐づく UI サイドカーファイルの絶対パスを返す。

    Args:
        workflow_path: 対象 workflow ファイルパス。
        ui_state_path: 明示指定の UI サイドカーパス。

    Returns:
        UI サイドカーファイルの絶対パス。
    """
    if ui_state_path is not None:
        return Path(ui_state_path).expanduser().resolve()
    workflow_abspath = Path(workflow_path).expanduser().resolve()
    return workflow_abspath.with_suffix(UI_STATE_SUFFIX)


def load_workflow_edit_session(
    workflow_path: str | PathLike[str],
    bundle_root: str | PathLike[str] | None = None,
    ui_state_path: str | PathLike[str] | None = None,
) -> WorkflowEditSession:
    """Workflow と UI サイドカーを読み込み編集セッションを返す。

    Args:
        workflow_path: 読み込み対象 workflow ファイルパス。
        bundle_root: 分割参照解決の基準ディレクトリ。
        ui_state_path: UI サイドカーファイルパス。

    Returns:
        現在状態を保持した `WorkflowEditSession`。

    Raises:
        ValueError: workflow/ui_state が辞書として読み込めない場合。
    """
    workflow_abspath = Path(workflow_path).expanduser().resolve()
    ui_state_abspath = resolve_ui_state_path(
        workflow_path=workflow_abspath,
        ui_state_path=ui_state_path,
    )

    workflow_payload = _load_workflow_mapping(workflow_abspath)
    ui_state_payload = _load_ui_state_mapping(ui_state_abspath)
    validation_report = validate_workflow_payload_for_ui(
        payload=deepcopy(workflow_payload),
        workflow_path=workflow_abspath,
        bundle_root=bundle_root,
    )
    revision = compute_workflow_revision(workflow_payload, ui_state_payload)
    return WorkflowEditSession(
        workflow=workflow_payload,
        ui_state=ui_state_payload,
        revision=revision,
        validation_report=validation_report,
    )


def build_workflow_diff(
    base_workflow: Mapping[str, Any],
    candidate_workflow: Mapping[str, Any],
    base_ui_state: Mapping[str, Any],
    candidate_ui_state: Mapping[str, Any],
    workflow_path: str | PathLike[str],
    bundle_root: str | PathLike[str] | None = None,
) -> WorkflowDiffResult:
    """Workflow 編集案の差分情報を生成する。

    Args:
        base_workflow: 現在の workflow データ。
        candidate_workflow: 編集後 workflow データ。
        base_ui_state: 現在の UI サイドカー。
        candidate_ui_state: 編集後 UI サイドカー。
        workflow_path: workflow ファイルパス。
        bundle_root: 分割参照解決の基準ディレクトリ。

    Returns:
        差分と検証結果を保持した `WorkflowDiffResult`。

    Raises:
        ValueError: workflow/ui_state が辞書形式でない場合。
    """
    base_workflow_mapping = _ensure_mapping(base_workflow, label="base workflow")
    candidate_workflow_mapping = _ensure_mapping(candidate_workflow, label="candidate workflow")
    base_ui_state_mapping = _ensure_mapping(base_ui_state, label="base ui_state")
    candidate_ui_state_mapping = _ensure_mapping(candidate_ui_state, label="candidate ui_state")

    changes = _collect_changes(
        before=base_workflow_mapping,
        after=candidate_workflow_mapping,
        path=(),
    )
    changes.extend(
        _collect_changes(
            before=base_ui_state_mapping,
            after=candidate_ui_state_mapping,
            path=("ui_state",),
        )
    )
    summary = _build_summary(changes)
    diff_text = _build_yaml_unified_diff(
        before=base_workflow_mapping,
        after=candidate_workflow_mapping,
    )
    validation_report = validate_workflow_payload_for_ui(
        payload=deepcopy(candidate_workflow_mapping),
        workflow_path=workflow_path,
        bundle_root=bundle_root,
    )

    return WorkflowDiffResult(
        base_revision=compute_workflow_revision(base_workflow_mapping, base_ui_state_mapping),
        candidate_revision=compute_workflow_revision(
            candidate_workflow_mapping,
            candidate_ui_state_mapping,
        ),
        summary=summary,
        changes=tuple(changes),
        yaml_unified_diff=diff_text,
        validation_report=validation_report,
    )


def compute_workflow_revision(
    workflow: Mapping[str, Any],
    ui_state: Mapping[str, Any],
) -> str:
    """Workflow と UI サイドカーの内容から revision を計算する。

    Args:
        workflow: workflow データ。
        ui_state: UI サイドカーデータ。

    Returns:
        SHA256 ベースの revision 文字列。
    """
    workflow_mapping = _ensure_mapping(workflow, label="workflow")
    ui_state_mapping = _ensure_mapping(ui_state, label="ui_state")
    payload = {"ui_state": ui_state_mapping, "workflow": workflow_mapping}
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def _load_workflow_mapping(path: Path) -> dict[str, Any]:
    """Workflow YAML を辞書として読み込む。

    Args:
        path: 読み込み対象の workflow パス。

    Returns:
        読み込んだ workflow 辞書。

    Raises:
        ValueError: YAML の読み込みに失敗した場合。
    """
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"workflow の読み込みに失敗しました: {path}: {exc}") from exc
    return _ensure_mapping(payload, label=f"workflow: {path}")


def _load_ui_state_mapping(path: Path) -> dict[str, Any]:
    """UI サイドカー JSON を辞書として読み込む。

    Args:
        path: 読み込み対象の UI サイドカーパス。

    Returns:
        読み込んだ UI サイドカー辞書。未存在時は空辞書。

    Raises:
        ValueError: JSON が辞書形式でない場合。
    """
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"ui_state の読み込みに失敗しました: {path}: {exc}") from exc
    return _ensure_mapping(payload, label=f"ui_state: {path}")


def _ensure_mapping(payload: Any, label: str) -> dict[str, Any]:
    """辞書形式であることを検証して返す。

    Args:
        payload: 検証対象データ。
        label: エラーメッセージに含める対象名。

    Returns:
        辞書化されたデータの shallow copy。

    Raises:
        ValueError: payload が辞書でない場合。
    """
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return dict(payload)


def _collect_changes(before: Any, after: Any, path: Location) -> list[WorkflowChange]:
    """2つの値を再帰比較して変更イベントを抽出する。

    Args:
        before: 変更前の値。
        after: 変更後の値。
        path: 現在の走査パス。

    Returns:
        抽出した変更イベント一覧。
    """
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        changes: list[WorkflowChange] = []
        before_mapping = dict(before)
        after_mapping = dict(after)
        keys = sorted(set(before_mapping) | set(after_mapping), key=lambda item: str(item))
        for key in keys:
            token = _path_token(key)
            child_path = path + (token,)
            if key not in before_mapping:
                changes.append(
                    WorkflowChange(
                        kind="add",
                        path=child_path,
                        before=None,
                        after=deepcopy(after_mapping[key]),
                    )
                )
                continue
            if key not in after_mapping:
                changes.append(
                    WorkflowChange(
                        kind="remove",
                        path=child_path,
                        before=deepcopy(before_mapping[key]),
                        after=None,
                    )
                )
                continue
            changes.extend(
                _collect_changes(
                    before=before_mapping[key],
                    after=after_mapping[key],
                    path=child_path,
                )
            )
        return changes

    if isinstance(before, list) and isinstance(after, list):
        changes = []
        max_length = max(len(before), len(after))
        for index in range(max_length):
            child_path = path + (index,)
            if index >= len(before):
                changes.append(
                    WorkflowChange(
                        kind="add",
                        path=child_path,
                        before=None,
                        after=deepcopy(after[index]),
                    )
                )
                continue
            if index >= len(after):
                changes.append(
                    WorkflowChange(
                        kind="remove",
                        path=child_path,
                        before=deepcopy(before[index]),
                        after=None,
                    )
                )
                continue
            changes.extend(
                _collect_changes(
                    before=before[index],
                    after=after[index],
                    path=child_path,
                )
            )
        return changes

    if before != after:
        return [
            WorkflowChange(
                kind="update",
                path=path,
                before=deepcopy(before),
                after=deepcopy(after),
            )
        ]
    return []


def _build_summary(changes: list[WorkflowChange]) -> dict[str, int]:
    """変更イベントをカテゴリ別件数へ集計する。

    Args:
        changes: 集計対象の変更イベント一覧。

    Returns:
        カテゴリ別件数を保持する辞書。
    """
    summary = {
        "total": len(changes),
        "nodes": 0,
        "edges": 0,
        "params": 0,
        "ui_state": 0,
        "other": 0,
    }
    for change in changes:
        if not change.path:
            summary["other"] += 1
            continue
        category = change.path[0]
        if category == "nodes":
            summary["nodes"] += 1
        elif category == "edges":
            summary["edges"] += 1
        elif category == "params":
            summary["params"] += 1
        elif category == "ui_state":
            summary["ui_state"] += 1
        else:
            summary["other"] += 1
    return summary


def _build_yaml_unified_diff(before: dict[str, Any], after: dict[str, Any]) -> str:
    """Workflow YAML の unified diff 文字列を生成する。

    Args:
        before: 変更前 workflow。
        after: 変更後 workflow。

    Returns:
        unified diff 文字列。差分がない場合は空文字列。
    """
    before_text = yaml.safe_dump(before, sort_keys=False, allow_unicode=True)
    after_text = yaml.safe_dump(after, sort_keys=False, allow_unicode=True)
    lines = unified_diff(
        before_text.splitlines(),
        after_text.splitlines(),
        fromfile="current/workflow.yaml",
        tofile="candidate/workflow.yaml",
        lineterm="",
    )
    return "\n".join(lines)


def _path_token(value: Any) -> str | int:
    """辞書キーを変更パスのトークンへ正規化する。

    Args:
        value: 変換対象の辞書キー。

    Returns:
        パス表現に利用するトークン。
    """
    if isinstance(value, (str, int)):
        return value
    return str(value)
