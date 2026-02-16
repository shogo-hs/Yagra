"""Workflow フォーム編集向けの表示モデルを生成する。"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any

import yaml

from yagra.application.use_cases.workflow_edit_session import compute_workflow_revision


@dataclass(frozen=True, slots=True)
class WorkflowNodeFormItem:
    """フォーム編集用のノード表示情報を保持する。"""

    id: str
    handler: str
    prompt_ref: str | None
    model: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        """API 応答形式の辞書へ変換する。

        Returns:
            id, handler, prompt_ref, model を含む辞書。
        """
        return {
            "id": self.id,
            "handler": self.handler,
            "prompt_ref": self.prompt_ref,
            "model": self.model,
        }


@dataclass(frozen=True, slots=True)
class WorkflowEdgeFormItem:
    """フォーム編集用のエッジ表示情報を保持する。"""

    index: int
    source: str
    target: str
    condition: str | None

    def to_dict(self) -> dict[str, Any]:
        """API 応答形式の辞書へ変換する。

        Returns:
            index, source, target, condition を含む辞書。
        """
        return {
            "index": self.index,
            "source": self.source,
            "target": self.target,
            "condition": self.condition,
        }


@dataclass(frozen=True, slots=True)
class WorkflowFormView:
    """フォーム編集画面の表示モデルを保持する。"""

    revision: str
    nodes: tuple[WorkflowNodeFormItem, ...]
    edges: tuple[WorkflowEdgeFormItem, ...]
    prompt_catalog_keys: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """API 応答形式の辞書へ変換する。

        Returns:
            revision, nodes, edges, prompt_catalog_keys を含む辞書。
        """
        return {
            "revision": self.revision,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "prompt_catalog_keys": list(self.prompt_catalog_keys),
        }


@dataclass(frozen=True, slots=True)
class WorkflowCatalogIssue:
    """catalog 読み込み時の問題を表す。"""

    code: str
    message: str
    location: tuple[str | int, ...]

    def to_dict(self) -> dict[str, Any]:
        """API 応答形式の辞書へ変換する。

        Returns:
            code, message, location を含む辞書。
        """
        return {"code": self.code, "message": self.message, "location": list(self.location)}


@dataclass(frozen=True, slots=True)
class WorkflowCatalogPreview:
    """workflow.params の catalog 設定プレビューを表す。"""

    prompt_catalog_path: str | None
    prompt_catalog_keys: tuple[str, ...]
    issues: tuple[WorkflowCatalogIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        """API 応答形式の辞書へ変換する。

        Returns:
            prompt_catalog_path, prompt_catalog_keys, issues を含む辞書。
        """
        return {
            "prompt_catalog_path": self.prompt_catalog_path,
            "prompt_catalog_keys": list(self.prompt_catalog_keys),
            "issues": [issue.to_dict() for issue in self.issues],
        }


def build_workflow_form_view(
    workflow: Mapping[str, Any],
    ui_state: Mapping[str, Any],
    workflow_path: str | PathLike[str],
    bundle_root: str | PathLike[str] | None = None,
) -> WorkflowFormView:
    """Workflow と UI 状態からフォーム編集向け表示モデルを生成する。

    Args:
        workflow: 表示対象の workflow データ。
        ui_state: 現在の UI サイドカーデータ。
        workflow_path: workflow ファイルパス。
        bundle_root: 分割参照解決の基準ディレクトリ。

    Returns:
        フォーム表示に必要な情報を含む `WorkflowFormView`。

    Raises:
        ValueError: workflow の構造が想定外の場合。
    """
    workflow_mapping = _ensure_mapping(workflow, label="workflow")
    ui_state_mapping = _ensure_mapping(ui_state, label="ui_state")
    nodes_raw = workflow_mapping.get("nodes", [])
    edges_raw = workflow_mapping.get("edges", [])
    if nodes_raw is None:
        nodes_raw = []
    if edges_raw is None:
        edges_raw = []
    if not isinstance(nodes_raw, list):
        raise ValueError("workflow.nodes must be a list when present")
    if not isinstance(edges_raw, list):
        raise ValueError("workflow.edges must be a list when present")

    nodes: list[WorkflowNodeFormItem] = []
    for node_raw in nodes_raw:
        if not isinstance(node_raw, Mapping):
            continue
        node = dict(node_raw)
        node_id = node.get("id")
        handler = node.get("handler")
        if not isinstance(node_id, str) or not isinstance(handler, str):
            continue
        params = node.get("params")
        if params is None:
            params = {}
        if not isinstance(params, Mapping):
            continue
        params_mapping = dict(params)
        nodes.append(
            WorkflowNodeFormItem(
                id=node_id,
                handler=handler,
                prompt_ref=_as_optional_string(params_mapping.get("prompt_ref")),
                model=_as_optional_mapping(params_mapping.get("model")),
            )
        )

    edges: list[WorkflowEdgeFormItem] = []
    for index, edge_raw in enumerate(edges_raw):
        if not isinstance(edge_raw, Mapping):
            continue
        edge = dict(edge_raw)
        source = edge.get("source")
        target = edge.get("target")
        condition = edge.get("condition")
        if not isinstance(source, str) or not isinstance(target, str):
            continue
        if condition is not None and not isinstance(condition, str):
            continue
        edges.append(
            WorkflowEdgeFormItem(
                index=index,
                source=source,
                target=target,
                condition=condition,
            )
        )

    workflow_abspath = Path(workflow_path).expanduser().resolve()
    bundle_root_path = Path(bundle_root).expanduser().resolve() if bundle_root is not None else None
    catalog_preview = build_workflow_catalog_preview(
        workflow=workflow_mapping,
        workflow_path=workflow_abspath,
        bundle_root=bundle_root_path,
    )

    return WorkflowFormView(
        revision=compute_workflow_revision(workflow_mapping, ui_state_mapping),
        nodes=tuple(nodes),
        edges=tuple(edges),
        prompt_catalog_keys=catalog_preview.prompt_catalog_keys,
    )


def build_workflow_catalog_preview(
    workflow: Mapping[str, Any],
    workflow_path: str | PathLike[str],
    bundle_root: str | PathLike[str] | None = None,
) -> WorkflowCatalogPreview:
    """workflow.params の catalog 設定を解決し、候補キーと問題を返す。

    Args:
        workflow: workflow データ。
        workflow_path: workflow ファイルパス。
        bundle_root: 分割参照解決の基準ディレクトリ。

    Returns:
        catalog 設定プレビュー。
    """
    workflow_mapping = _ensure_mapping(workflow, label="workflow")
    workflow_abspath = Path(workflow_path).expanduser().resolve()
    bundle_root_path = Path(bundle_root).expanduser().resolve() if bundle_root is not None else None
    params_raw = workflow_mapping.get("params")
    if params_raw is None:
        params_raw = {}
    if not isinstance(params_raw, Mapping):
        return WorkflowCatalogPreview(
            prompt_catalog_path=None,
            prompt_catalog_keys=(),
            issues=(
                WorkflowCatalogIssue(
                    code="invalid_workflow_params",
                    message="workflow.params must be a mapping",
                    location=("params",),
                ),
            ),
        )

    params = dict(params_raw)
    prompt_catalog_path, prompt_catalog_keys, prompt_issues = _resolve_catalog_setting(
        workflow_abspath=workflow_abspath,
        bundle_root=bundle_root_path,
        params=params,
        catalog_name="prompt_catalog",
    )
    return WorkflowCatalogPreview(
        prompt_catalog_path=prompt_catalog_path,
        prompt_catalog_keys=prompt_catalog_keys,
        issues=tuple(prompt_issues),
    )


def _resolve_catalog_setting(
    workflow_abspath: Path,
    bundle_root: Path | None,
    params: Mapping[str, Any],
    catalog_name: str,
) -> tuple[str | None, tuple[str, ...], list[WorkflowCatalogIssue]]:
    """単一 catalog 設定を解決し、キー候補と問題を返す。"""
    location = ("params", catalog_name)
    catalog_path_raw = params.get(catalog_name)
    if catalog_path_raw is None:
        return None, (), []
    if not isinstance(catalog_path_raw, str):
        return (
            None,
            (),
            [
                WorkflowCatalogIssue(
                    code="catalog_path_type_error",
                    message=f"{catalog_name} must be a string",
                    location=location,
                )
            ],
        )
    if not catalog_path_raw.strip():
        return None, (), []

    catalog_path = _resolve_catalog_path(
        catalog_path=catalog_path_raw.strip(),
        workflow_abspath=workflow_abspath,
        bundle_root=bundle_root,
    )
    catalog_abspath = str(catalog_path)
    if not catalog_path.exists():
        return (
            catalog_abspath,
            (),
            [
                WorkflowCatalogIssue(
                    code="catalog_not_found",
                    message=f"catalog file not found: {catalog_path}",
                    location=location,
                )
            ],
        )

    try:
        with catalog_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        return (
            catalog_abspath,
            (),
            [
                WorkflowCatalogIssue(
                    code="catalog_load_error",
                    message=f"catalog file load failed: {catalog_path}: {exc}",
                    location=location,
                )
            ],
        )

    if not isinstance(payload, Mapping):
        return (
            catalog_abspath,
            (),
            [
                WorkflowCatalogIssue(
                    code="catalog_not_mapping",
                    message=f"catalog must be a mapping: {catalog_path}",
                    location=location,
                )
            ],
        )

    key_paths = _collect_key_paths(dict(payload), prefix="")
    return catalog_abspath, tuple(sorted(set(key_paths))), []


def _resolve_catalog_path(
    catalog_path: str, workflow_abspath: Path, bundle_root: Path | None
) -> Path:
    """Catalog パスを workflow 基準で絶対パスへ解決する。

    Args:
        catalog_path: workflow で指定された catalog パス。
        workflow_abspath: workflow 絶対パス。
        bundle_root: 分割参照解決の基準ディレクトリ。

    Returns:
        解決後の絶対パス。
    """
    raw_path = Path(catalog_path)
    if raw_path.is_absolute():
        return raw_path.resolve()
    if bundle_root is not None:
        return (bundle_root / raw_path).resolve()
    return (workflow_abspath.parent / raw_path).resolve()


def _collect_key_paths(payload: dict[str, Any], prefix: str) -> list[str]:
    """辞書を再帰走査し `a.b.c` 形式のキー一覧を返す。

    Args:
        payload: 走査対象の辞書。
        prefix: 親キー接頭辞。

    Returns:
        収集したキー一覧。
    """
    paths: list[str] = []
    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        current = f"{prefix}.{key}" if prefix else key
        paths.append(current)
        if isinstance(value, Mapping):
            paths.extend(_collect_key_paths(dict(value), prefix=current))
    return paths


def _as_optional_mapping(value: Any) -> dict[str, Any] | None:
    """値を任意辞書として正規化する。

    Args:
        value: 変換対象値。

    Returns:
        辞書値、または `None`。
    """
    if not isinstance(value, Mapping):
        return None
    return deepcopy(dict(value))


def _as_optional_string(value: Any) -> str | None:
    """値を任意文字列として正規化する。

    Args:
        value: 変換対象値。

    Returns:
        文字列値、または `None`。
    """
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def _ensure_mapping(payload: Mapping[str, Any], label: str) -> dict[str, Any]:
    """入力が辞書互換であることを検証して辞書化する。

    Args:
        payload: 検証対象データ。
        label: エラー文言で使う入力名。

    Returns:
        shallow copy した辞書データ。

    Raises:
        ValueError: payload が辞書互換でない場合。
    """
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return dict(payload)
