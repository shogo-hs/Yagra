"""Output port contract for golden test case persistence (G-20)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from yagra.domain.entities.golden_case import GoldenCase


class GoldenCaseRepositoryError(OSError):
    """Raised when golden case persistence operations fail."""


class GoldenCaseNotFoundError(GoldenCaseRepositoryError):
    """Raised when a requested golden case does not exist."""


class GoldenCaseRepositoryPort(ABC):
    """Abstract contract for persisting and retrieving golden test cases.

    Implementations may write to local files, remote storage, or in-memory
    stores. The default implementation writes JSON files to .yagra/golden/.
    """

    @abstractmethod
    def save(self, case: GoldenCase) -> str:
        """Persists the golden case and returns the destination identifier.

        Args:
            case: The golden case to save.

        Returns:
            Destination string (e.g. file path for local implementations).

        Raises:
            GoldenCaseRepositoryError: If writing fails.
        """

    @abstractmethod
    def load(self, workflow_name: str, case_name: str) -> GoldenCase:
        """Loads a golden case by workflow name and case name.

        Args:
            workflow_name: Name of the workflow (YAML file stem).
            case_name: Name of the golden case.

        Returns:
            The loaded GoldenCase.

        Raises:
            GoldenCaseNotFoundError: If the case does not exist.
            GoldenCaseRepositoryError: If reading fails.
        """

    @abstractmethod
    def list(self, workflow_name: str | None = None) -> list[GoldenCase]:
        """Lists golden cases, optionally filtered by workflow name.

        Args:
            workflow_name: If provided, only returns cases for this workflow.
                If None, returns all cases.

        Returns:
            List of golden cases, sorted by workflow_name then case_name.

        Raises:
            GoldenCaseRepositoryError: If listing fails.
        """

    @abstractmethod
    def delete(self, workflow_name: str, case_name: str) -> bool:
        """Deletes a golden case by workflow name and case name.

        Args:
            workflow_name: Name of the workflow (YAML file stem).
            case_name: Name of the golden case.

        Returns:
            True if the case was deleted, False if it did not exist.

        Raises:
            GoldenCaseRepositoryError: If deletion fails.
        """

    @abstractmethod
    def exists(self, workflow_name: str, case_name: str) -> bool:
        """Checks whether a golden case exists.

        Args:
            workflow_name: Name of the workflow (YAML file stem).
            case_name: Name of the golden case.

        Returns:
            True if the case exists, False otherwise.
        """
