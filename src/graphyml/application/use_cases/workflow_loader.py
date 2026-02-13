"""workflow.yaml を読み込み、GraphSpec へ変換する。"""

from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import Any

import yaml

from graphyml.application.services import resolve_workflow_references
from graphyml.domain.entities import GraphSpec
from graphyml.domain.services import validate_graph_spec


def load_graph_spec_from_workflow(
    workflow_path: str | PathLike[str],
    bundle_root: str | PathLike[str] | None = None,
) -> GraphSpec:
    """Workflow ファイルを読み込み、参照解決後に `GraphSpec` を返す。

    Args:
        workflow_path: 入口となる workflow YAML のパス。
        bundle_root: 分割参照時の基準ディレクトリ。未指定時は workflow 親を使う。

    Returns:
        参照解決・スキーマ検証済みの `GraphSpec`。

    Raises:
        ValueError: workflow が辞書形式でない場合。
    """
    workflow_abspath = Path(workflow_path).expanduser().resolve()
    payload = _load_yaml_mapping(workflow_abspath)

    bundle_root_path: Path | None = None
    if bundle_root is not None:
        bundle_root_path = Path(bundle_root).expanduser().resolve()

    resolved_payload = resolve_workflow_references(
        payload=payload,
        workflow_path=workflow_abspath,
        bundle_root=bundle_root_path,
    )
    return validate_graph_spec(resolved_payload)


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    """YAML ファイルを辞書として読み込む。"""
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"workflow must be a mapping: {path}")
    return data
