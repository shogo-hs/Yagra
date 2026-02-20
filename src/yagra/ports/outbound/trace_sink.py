"""Output port contract for writing execution traces (G-14)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from yagra.domain.entities.trace import WorkflowRunTrace


class TraceSinkError(OSError):
    """Raised when trace persistence fails."""


class TraceSinkPort(ABC):
    """Abstract contract for persisting a WorkflowRunTrace.

    Implementations may write to local files, remote APIs, or in-memory stores.
    The default implementation writes structured JSON to .yagra/traces/.
    """

    @abstractmethod
    def write(self, trace: WorkflowRunTrace) -> str:
        """Persists the trace and returns the destination identifier.

        Args:
            trace: Completed workflow run trace to persist.

        Returns:
            Destination string (file path for local implementations,
            URL for remote implementations, etc.).

        Raises:
            TraceSinkError: If writing fails.
        """

    @abstractmethod
    def flush(self) -> None:
        """Ensures all buffered data is committed.

        For file-based sinks, this is typically a no-op since write() is
        synchronous. Reserved for future async or batched implementations.
        """
