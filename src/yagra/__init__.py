"""Yagra パッケージの公開 API。"""

from __future__ import annotations

from collections.abc import Mapping
from os import PathLike
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from yagra.adapters.outbound import InMemoryNodeRegistry
from yagra.application.use_cases import build_from_workflow_path
from yagra.ports.outbound import NodeHandler, NodeRegistryPort


class Yagra:
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
        registry: NodeRegistryPort | Mapping[str, NodeHandler],
        bundle_root: str | PathLike[str] | None = None,
        state_schema: Any = dict,
    ) -> Yagra:
        """ワークフローファイルから `Yagra` インスタンスを生成する。

        Args:
            workflow_path: 入口となる `workflow.yaml` のパス。
            registry: handler 名を callable へ解決するレジストリ実装、または handler マッピング。
            bundle_root: 分割参照の解決に使う基準ディレクトリ。未指定時は workflow 親ディレクトリ。
            state_schema: LangGraph の状態スキーマ。既定は `dict`。

        Returns:
            コンパイル済みグラフを内包した `Yagra` インスタンス。
        """
        normalized_registry = _normalize_registry(registry)
        compiled = build_from_workflow_path(
            workflow_path=workflow_path,
            registry=normalized_registry,
            bundle_root=bundle_root,
            state_schema=state_schema,
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
    """Yagra の初期化状態を標準出力へ表示する。"""
    print("Yagra bootstrap is ready.")


def _normalize_registry(registry: NodeRegistryPort | Mapping[str, NodeHandler]) -> NodeRegistryPort:
    """Registry 引数を `NodeRegistryPort` 実装へ正規化する。

    Args:
        registry: レジストリ実装、または handler のマッピング。

    Returns:
        `NodeRegistryPort` 実装。

    Raises:
        TypeError: 受け付けない型が渡された場合。
    """
    if isinstance(registry, NodeRegistryPort):
        return registry
    if isinstance(registry, Mapping):
        return InMemoryNodeRegistry(registry)
    raise TypeError("registry must be NodeRegistryPort or mapping[str, NodeHandler]")


__all__ = ["Yagra", "main"]
