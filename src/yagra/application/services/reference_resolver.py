"""workflow から prompt/model 参照を解決する。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
    """Workflow の `prompt_ref` / `model_ref` を解決する。

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

    prompt_catalog = _as_optional_string(
        params.get("prompt_catalog"),
        location=("params", "prompt_catalog"),
    )
    model_catalog = _as_optional_string(
        params.get("model_catalog"),
        location=("params", "model_catalog"),
    )

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

        prompt_ref = _as_optional_string(
            node_params.get("prompt_ref"),
            location=("nodes", index, "params", "prompt_ref"),
        )
        if prompt_ref is not None:
            node_params["prompt"] = _resolve_reference(
                reference=prompt_ref,
                default_catalog=prompt_catalog,
                workflow_path=workflow_path,
                bundle_root=bundle_root,
                ref_label="prompt_ref",
                location=("nodes", index, "params", "prompt_ref"),
            )

        model_ref = _as_optional_string(
            node_params.get("model_ref"),
            location=("nodes", index, "params", "model_ref"),
        )
        if model_ref is not None:
            resolved_model = _resolve_reference(
                reference=model_ref,
                default_catalog=model_catalog,
                workflow_path=workflow_path,
                bundle_root=bundle_root,
                ref_label="model_ref",
                location=("nodes", index, "params", "model_ref"),
            )
            model_override = _as_optional_mapping(
                node_params.get("model"),
                location=("nodes", index, "params", "model"),
            )
            if model_override is None:
                node_params["model"] = resolved_model
                continue
            if not isinstance(resolved_model, Mapping):
                raise WorkflowReferenceError(
                    "model_ref must resolve to a mapping when model override is provided",
                    location=("nodes", index, "params", "model_ref"),
                )
            node_params["model"] = _merge_mapping(
                base=deepcopy(dict(resolved_model)),
                override=model_override,
            )

    return resolved


def _resolve_reference(
    reference: str,
    default_catalog: str | None,
    workflow_path: Path,
    bundle_root: Path | None,
    ref_label: str,
    location: Location = (),
) -> Any:
    """単一参照を読み込み・解決する。

    Args:
        reference: 解決対象の参照文字列。
        default_catalog: 既定カタログパス。
        workflow_path: 入口 workflow の絶対パス。
        bundle_root: 参照解決基準ディレクトリ。
        ref_label: エラー文言向けの参照ラベル。
        location: 問題発生箇所の workflow パス。

    Returns:
        参照解決済みの値。

    Raises:
        WorkflowReferenceError: 参照文字列や参照先が不正な場合。
    """
    if "#" in reference:
        raw_path, key_path = reference.split("#", 1)
        catalog_path = raw_path.strip()
        if not catalog_path:
            raise WorkflowReferenceError(
                f"{ref_label} path is empty: {reference}",
                location=location,
            )
    else:
        if default_catalog is None:
            raise WorkflowReferenceError(
                f"{ref_label} requires '<path>#<key>' format or workflow.params catalog",
                location=location,
            )
        catalog_path = default_catalog
        key_path = reference

    key_path = key_path.strip()
    if not key_path:
        raise WorkflowReferenceError(
            f"{ref_label} key is empty: {reference}",
            location=location,
        )

    target_path = _resolve_catalog_path(
        catalog_path=catalog_path,
        workflow_path=workflow_path,
        bundle_root=bundle_root,
    )
    catalog_data = _load_yaml_file(target_path, location=location)
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
        path = raw
    elif bundle_root is not None:
        path = bundle_root / raw
    else:
        path = workflow_path.parent / raw
    return path.resolve()


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


def _as_optional_mapping(value: Any, location: Location = ()) -> dict[str, Any] | None:
    """値を任意辞書として正規化する。"""
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise WorkflowReferenceError("override value must be a mapping", location=location)
    return deepcopy(dict(value))


def _merge_mapping(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """辞書を再帰マージし、override 側を優先する。"""
    merged = deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], Mapping) and isinstance(value, Mapping):
            merged[key] = _merge_mapping(dict(merged[key]), dict(value))
            continue
        merged[key] = deepcopy(value)
    return merged
