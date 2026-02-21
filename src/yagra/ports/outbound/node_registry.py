"""Defines the contract for Registry used in node handler resolution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

type NodeHandler = Callable[..., Any]


class NodeRegistryError(KeyError):
    """Base exception raised during node registry operations."""


class NodeHandlerAlreadyRegisteredError(NodeRegistryError):
    """Exception raised when a duplicate handler name is registered."""


class NodeHandlerNotFoundError(NodeRegistryError):
    """Exception raised when attempting to resolve an unregistered handler name."""


class NodeRegistryPort(ABC):
    """Abstract contract providing registration and resolution of node handlers."""

    @abstractmethod
    def register(self, name: str, handler: NodeHandler) -> None:
        """Registers a handler name and callable to the registry.

        Args:
            name: Unique name identifying the handler.
            handler: Callable executing node processing.

        Raises:
            NodeHandlerAlreadyRegisteredError: If a handler with the same name is already registered.
        """

    @abstractmethod
    def resolve(self, name: str) -> NodeHandler:
        """Resolves the callable corresponding to the handler name.

        Args:
            name: Handler name to resolve.

        Returns:
            Callable registered with the specified name.

        Raises:
            NodeHandlerNotFoundError: If the specified handler name is not registered.
        """

    def resolve_for_node(self, name: str, node_id: str) -> NodeHandler:
        """Resolves the callable for a specific node instance.

        When multiple nodes share the same handler name (e.g., two nodes both
        using ``"llm"``), this method allows returning a different callable per
        node. The default implementation delegates to :meth:`resolve`, ignoring
        ``node_id``. Subclasses (such as golden-test mock registries) may
        override this to provide per-node dispatch.

        Args:
            name: Handler name to resolve.
            node_id: Unique identifier of the node requesting the handler.

        Returns:
            Callable appropriate for the given node.

        Raises:
            NodeHandlerNotFoundError: If the handler cannot be resolved.
        """
        return self.resolve(name)
