"""Registry implementation managing node handlers in memory."""

from __future__ import annotations

from collections.abc import Mapping

from yagra.ports.outbound import (
    NodeHandler,
    NodeHandlerAlreadyRegisteredError,
    NodeHandlerNotFoundError,
    NodeRegistryPort,
)


class InMemoryNodeRegistry(NodeRegistryPort):
    """In-memory implementation holding node handlers in a dictionary."""

    def __init__(self, initial_handlers: Mapping[str, NodeHandler] | None = None) -> None:
        """Initializes the registry with initial handlers.

        Args:
            initial_handlers: List of handlers to register initially. Starts empty if not specified.
        """
        self._handlers: dict[str, NodeHandler] = {}
        if initial_handlers is None:
            return

        for name, handler in initial_handlers.items():
            self.register(name, handler)

    def register(self, name: str, handler: NodeHandler) -> None:
        """Registers a handler name and callable.

        Args:
            name: Handler identifier name.
            handler: Callable to be invoked during node execution.

        Raises:
            NodeHandlerAlreadyRegisteredError: If a handler with the same name is already registered.
        """
        if name in self._handlers:
            raise NodeHandlerAlreadyRegisteredError(f"handler is already registered: {name}")
        self._handlers[name] = handler

    def resolve(self, name: str) -> NodeHandler:
        """Resolves callable from handler name.

        Args:
            name: Handler name to resolve.

        Returns:
            Registered callable.

        Raises:
            NodeHandlerNotFoundError: If the specified handler name is not registered.
        """
        if name not in self._handlers:
            raise NodeHandlerNotFoundError(f"handler is not registered: {name}")
        return self._handlers[name]
