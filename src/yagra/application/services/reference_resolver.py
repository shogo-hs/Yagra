"""workflow の `prompt_ref` 参照を解決する。"""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

type Location = tuple[str | int, ...]


class WorkflowReferenceError(ValueError):
    """workflow 内の分割参照解決に失敗した場合の例外。"""

    def __init__(self, message: str, location: Sequence[str | int] | None = None) -> None:
        """例外メッセージと問題位置を初期化する。

        Args:
            message: 失敗理由を表すメッセージ。
            location: 問題が発生した workflow 内のパス。
        """
        super().__init__(message)
        self.location: Location = tuple(location or ())


def resolve_workflow_references(
    payload: dict[str, Any],
    workflow_path: Path,
    bundle_root: Path | None = None,
) -> dict[str, Any]:
    """Workflow の `prompt_ref` を解決する。

    Args:
        payload: `workflow.yaml` を辞書化したデータ。
        workflow_path: 入口 workflow ファイルの絶対パス。
        bundle_root: 分割参照時の基準ディレクトリ。未指定時は workflow 親を使う。

    Returns:
        参照解決後の workflow データ。

    Raises:
        WorkflowReferenceError: 参照形式不正、参照先未存在、キー未定義の場合。
    """
    resolved = deepcopy(payload)
    params = resolved.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise WorkflowReferenceError("workflow.params must be a mapping", location=("params",))
    resolved["params"] = params

    nodes = resolved.get("nodes")
    if not isinstance(nodes, list):
        return resolved

    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise WorkflowReferenceError(
                f"node[{index}] must be a mapping",
                location=("nodes", index),
            )

        node_params = node.get("params")
        if node_params is None:
            node_params = {}
            node["params"] = node_params
        if not isinstance(node_params, dict):
            raise WorkflowReferenceError(
                f"node[{index}].params must be a mapping",
                location=("nodes", index, "params"),
            )

        if "prompt" in node_params and node_params["prompt"] is not None:
            raise WorkflowReferenceError(
                "inline prompt is no longer supported; use prompt_ref to reference an external prompt file",
                location=("nodes", index, "params", "prompt"),
            )

        prompt_ref = _as_optional_string(
            node_params.get("prompt_ref"),
            location=("nodes", index, "params", "prompt_ref"),
        )
        if prompt_ref is not None:
            resolved_prompt = _resolve_reference(
                reference=prompt_ref,
                workflow_path=workflow_path,
                bundle_root=bundle_root,
                ref_label="prompt_ref",
                location=("nodes", index, "params", "prompt_ref"),
            )
            node_params["prompt"] = resolved_prompt

        if "model_ref" in node_params:
            raise WorkflowReferenceError(
                "model_ref is no longer supported; define params.model inline",
                location=("nodes", index, "params", "model_ref"),
            )

    return resolved


def _resolve_reference(
    reference: str,
    workflow_path: Path,
    bundle_root: Path | None,
    ref_label: str,
    location: Location = (),
) -> Any:
    """単一参照を読み込み・解決する。

    Args:
        reference: 解決対象の参照文字列。
        workflow_path: 入口 workflow の絶対パス。
        bundle_root: 参照解決基準ディレクトリ。
        ref_label: エラー文言向けの参照ラベル。
        location: 問題発生箇所の workflow パス。

    Returns:
        参照解決済みの値。

    Raises:
        WorkflowReferenceError: 参照文字列や参照先が不正な場合。
    """
    key_path: str | None = None
    if "#" in reference:
        raw_path, raw_key_path = reference.split("#", 1)
        catalog_path = raw_path.strip()
        if not catalog_path:
            raise WorkflowReferenceError(
                f"{ref_label} path is empty: {reference}",
                location=location,
            )
        key_path = raw_key_path.strip()
        if not key_path:
            raise WorkflowReferenceError(
                f"{ref_label} key is empty: {reference}",
                location=location,
            )
    else:
        catalog_path = reference.strip()
        if not catalog_path:
            raise WorkflowReferenceError(
                f"{ref_label} path is empty: {reference}",
                location=location,
            )

    target_path = _resolve_catalog_path(
        catalog_path=catalog_path,
        workflow_path=workflow_path,
        bundle_root=bundle_root,
    )
    catalog_data = _load_yaml_file(target_path, location=location)
    if key_path is None:
        return deepcopy(catalog_data)
    return _lookup_key_path(
        catalog_data,
        key_path,
        ref_label=ref_label,
        target_path=target_path,
        location=location,
    )


def _resolve_catalog_path(catalog_path: str, workflow_path: Path, bundle_root: Path | None) -> Path:
    """参照先 YAML の実パスを解決する。"""
    raw = Path(catalog_path)
    if raw.is_absolute():
        return raw.resolve()

    workflow_relative_path = (workflow_path.parent / raw).resolve()

    if bundle_root is not None:
        return (bundle_root / raw).resolve()

    if _has_explicit_relative_prefix(raw):
        return workflow_relative_path

    if workflow_relative_path.exists():
        return workflow_relative_path

    for ancestor in workflow_path.parents[1:]:
        candidate = (ancestor / raw).resolve()
        if candidate.exists():
            return candidate

    return workflow_relative_path


def _has_explicit_relative_prefix(path: Path) -> bool:
    """`./` や `../` を含む明示相対パスかどうかを返す。"""
    return any(part in {".", ".."} for part in path.parts)


def _load_yaml_file(path: Path, location: Location = ()) -> Any:
    """YAML ファイルを読み込む。

    Args:
        path: 読み込む YAML ファイルパス。
        location: 問題発生箇所の workflow パス。

    Returns:
        YAML をパースしたオブジェクト。

    Raises:
        WorkflowReferenceError: 参照ファイルが存在しない場合。
    """
    if not path.exists():
        raise WorkflowReferenceError(f"reference file not found: {path}", location=location)
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _lookup_key_path(
    data: Any,
    key_path: str,
    ref_label: str,
    target_path: Path,
    location: Location = (),
) -> Any:
    """`a.b.c` 形式のキーで YAML データを走査する。

    Args:
        data: 走査対象の YAML データ。
        key_path: ドット区切りのキー。
        ref_label: エラー文言向けの参照ラベル。
        target_path: 参照先カタログのパス。
        location: 問題発生箇所の workflow パス。

    Returns:
        参照解決済みの値。

    Raises:
        WorkflowReferenceError: キーが見つからない場合。
    """
    current = data
    for segment in key_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            raise WorkflowReferenceError(
                f"{ref_label} key not found: {key_path} (file: {target_path})",
                location=location,
            )
        current = current[segment]
    return deepcopy(current)


def _as_optional_string(value: Any, location: Location = ()) -> str | None:
    """値を任意文字列として正規化する。

    Args:
        value: 変換対象の値。
        location: 問題発生箇所の workflow パス。

    Returns:
        正規化済み文字列。空白文字列は `None`。

    Raises:
        WorkflowReferenceError: 文字列以外の値が与えられた場合。
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise WorkflowReferenceError("reference value must be a string", location=location)
    normalized = value.strip()
    if not normalized:
        return None
    return normalized
