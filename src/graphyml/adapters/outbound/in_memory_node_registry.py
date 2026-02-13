"""ノードハンドラをメモリ上で管理する Registry 実装。"""

from __future__ import annotations

from collections.abc import Mapping

from graphyml.ports.outbound import (
    NodeHandler,
    NodeHandlerAlreadyRegisteredError,
    NodeHandlerNotFoundError,
    NodeRegistryPort,
)


class InMemoryNodeRegistry(NodeRegistryPort):
    """ノードハンドラを辞書で保持する in-memory 実装。"""

    def __init__(self, initial_handlers: Mapping[str, NodeHandler] | None = None) -> None:
        """初期ハンドラを取り込んでレジストリを初期化する。

        Args:
            initial_handlers: 初期登録するハンドラ一覧。未指定時は空で開始する。
        """
        self._handlers: dict[str, NodeHandler] = {}
        if initial_handlers is None:
            return

        for name, handler in initial_handlers.items():
            self.register(name, handler)

    def register(self, name: str, handler: NodeHandler) -> None:
        """ハンドラ名と callable を登録する。

        Args:
            name: ハンドラ識別名。
            handler: ノード実行時に呼び出す callable。

        Raises:
            NodeHandlerAlreadyRegisteredError: 同名ハンドラが既に登録済みの場合。
        """
        if name in self._handlers:
            raise NodeHandlerAlreadyRegisteredError(f"handler is already registered: {name}")
        self._handlers[name] = handler

    def resolve(self, name: str) -> NodeHandler:
        """ハンドラ名から callable を解決する。

        Args:
            name: 解決対象のハンドラ名。

        Returns:
            登録済みの callable。

        Raises:
            NodeHandlerNotFoundError: 指定名ハンドラが未登録の場合。
        """
        if name not in self._handlers:
            raise NodeHandlerNotFoundError(f"handler is not registered: {name}")
        return self._handlers[name]
