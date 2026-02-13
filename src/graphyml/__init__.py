"""Graphyml パッケージの公開 API。"""

from __future__ import annotations

from collections.abc import Mapping
from os import PathLike
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from graphyml.application.use_cases import build_from_workflow_path
from graphyml.ports.outbound import NodeRegistryPort


class Graphyml:
    """ワークフロー YAML から構築した LangGraph を実行するラッパー。"""

    def __init__(self, compiled_graph: CompiledStateGraph) -> None:
        """コンパイル済みグラフを保持して初期化する。

        Args:
            compiled_graph: `build_state_graph` により生成されたコンパイル済みグラフ。
        """
        self._compiled_graph = compiled_graph

    @classmethod
    def from_workflow(
        cls,
        workflow_path: str | PathLike[str],
        registry: NodeRegistryPort,
        bundle_root: str | PathLike[str] | None = None,
    ) -> Graphyml:
        """ワークフローファイルから `Graphyml` インスタンスを生成する。

        Args:
            workflow_path: 入口となる `workflow.yaml` のパス。
            registry: handler 名を callable へ解決するレジストリ実装。
            bundle_root: 分割参照の解決に使う基準ディレクトリ。未指定時は workflow 親ディレクトリ。

        Returns:
            コンパイル済みグラフを内包した `Graphyml` インスタンス。
        """
        compiled = build_from_workflow_path(
            workflow_path=workflow_path,
            registry=registry,
            bundle_root=bundle_root,
        )
        return cls(compiled)

    @property
    def compiled_graph(self) -> CompiledStateGraph:
        """保持しているコンパイル済みグラフを返す。"""
        return self._compiled_graph

    def invoke(self, state: Mapping[str, Any]) -> dict[str, Any]:
        """初期状態を入力してグラフを実行する。

        Args:
            state: 実行開始時の状態辞書。

        Returns:
            実行後の状態辞書。

        Raises:
            TypeError: グラフ実行結果が辞書互換ではない場合。
        """
        result = self._compiled_graph.invoke(dict(state))
        if not isinstance(result, Mapping):
            raise TypeError("compiled graph returned non-mapping result")
        return dict(result)


def main() -> None:
    """Graphyml の初期化状態を標準出力へ表示する。"""
    print("Graphyml bootstrap is ready.")
