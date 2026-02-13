"""workflow から prompt/model 参照を解決する。"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


class WorkflowReferenceError(ValueError):
    """workflow 内の分割参照解決に失敗した場合の例外。"""


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
        raise WorkflowReferenceError("workflow.params must be a mapping")
    resolved["params"] = params

    prompt_catalog = _as_optional_string(params.get("prompt_catalog"))
    model_catalog = _as_optional_string(params.get("model_catalog"))

    nodes = resolved.get("nodes")
    if not isinstance(nodes, list):
        return resolved

    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise WorkflowReferenceError(f"node[{index}] must be a mapping")

        node_params = node.get("params")
        if node_params is None:
            node_params = {}
            node["params"] = node_params
        if not isinstance(node_params, dict):
            raise WorkflowReferenceError(f"node[{index}].params must be a mapping")

        prompt_ref = _as_optional_string(node_params.get("prompt_ref"))
        if prompt_ref is not None:
            node_params["prompt"] = _resolve_reference(
                reference=prompt_ref,
                default_catalog=prompt_catalog,
                workflow_path=workflow_path,
                bundle_root=bundle_root,
                ref_label="prompt_ref",
            )

        model_ref = _as_optional_string(node_params.get("model_ref"))
        if model_ref is not None:
            node_params["model"] = _resolve_reference(
                reference=model_ref,
                default_catalog=model_catalog,
                workflow_path=workflow_path,
                bundle_root=bundle_root,
                ref_label="model_ref",
            )

    return resolved


def _resolve_reference(
    reference: str,
    default_catalog: str | None,
    workflow_path: Path,
    bundle_root: Path | None,
    ref_label: str,
) -> Any:
    """単一参照を読み込み・解決する。"""
    if "#" in reference:
        raw_path, key_path = reference.split("#", 1)
        catalog_path = raw_path.strip()
        if not catalog_path:
            raise WorkflowReferenceError(f"{ref_label} path is empty: {reference}")
    else:
        if default_catalog is None:
            raise WorkflowReferenceError(
                f"{ref_label} requires '<path>#<key>' format or workflow.params catalog"
            )
        catalog_path = default_catalog
        key_path = reference

    key_path = key_path.strip()
    if not key_path:
        raise WorkflowReferenceError(f"{ref_label} key is empty: {reference}")

    target_path = _resolve_catalog_path(
        catalog_path=catalog_path,
        workflow_path=workflow_path,
        bundle_root=bundle_root,
    )
    catalog_data = _load_yaml_file(target_path)
    return _lookup_key_path(catalog_data, key_path, ref_label=ref_label, target_path=target_path)


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


def _load_yaml_file(path: Path) -> Any:
    """YAML ファイルを読み込む。"""
    if not path.exists():
        raise WorkflowReferenceError(f"reference file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _lookup_key_path(data: Any, key_path: str, ref_label: str, target_path: Path) -> Any:
    """`a.b.c` 形式のキーで YAML データを走査する。"""
    current = data
    for segment in key_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            raise WorkflowReferenceError(
                f"{ref_label} key not found: {key_path} (file: {target_path})"
            )
        current = current[segment]
    return deepcopy(current)


def _as_optional_string(value: Any) -> str | None:
    """値を任意文字列として正規化する。"""
    if value is None:
        return None
    if not isinstance(value, str):
        raise WorkflowReferenceError("reference value must be a string")
    normalized = value.strip()
    if not normalized:
        return None
    return normalized
