"""workflow.yaml を読み込み、GraphSpec へ変換する。"""

from __future__ import annotations

from os import PathLike

from yagra.application.use_cases.workflow_validation_reporter import load_validated_graph_spec
from yagra.domain.entities import GraphSpec


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
        WorkflowValidationFailedError: workflow 検証に失敗した場合。
    """
    return load_validated_graph_spec(workflow_path=workflow_path, bundle_root=bundle_root)
