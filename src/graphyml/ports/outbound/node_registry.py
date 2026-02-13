"""ノードハンドラ解決に利用する Registry の契約を定義する。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

type NodeHandler = Callable[..., Any]


class NodeRegistryError(KeyError):
    """ノードレジストリ操作で発生する基底例外。"""


class NodeHandlerAlreadyRegisteredError(NodeRegistryError):
    """重複するハンドラ名が登録された場合の例外。"""


class NodeHandlerNotFoundError(NodeRegistryError):
    """未登録のハンドラ名を解決しようとした場合の例外。"""


class NodeRegistryPort(ABC):
    """ノードハンドラの登録と解決を提供する抽象契約。"""

    @abstractmethod
    def register(self, name: str, handler: NodeHandler) -> None:
        """ハンドラ名と callable をレジストリへ登録する。

        Args:
            name: ハンドラを識別する一意な名前。
            handler: ノード処理を実行する callable。

        Raises:
            NodeHandlerAlreadyRegisteredError: 同名ハンドラが既に登録済みの場合。
        """

    @abstractmethod
    def resolve(self, name: str) -> NodeHandler:
        """ハンドラ名に対応する callable を解決する。

        Args:
            name: 解決対象のハンドラ名。

        Returns:
            指定名で登録済みの callable。

        Raises:
            NodeHandlerNotFoundError: 指定名のハンドラが未登録の場合。
        """
