"""Defines the inbound port contract for Workflow Studio."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class StudioError(Exception):
    """Application error returned by Studio operations."""

    error: str
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        """Returns a dictionary that can be converted to an API response."""
        payload: dict[str, Any] = {"error": self.error}
        if self.message is not None:
            payload["message"] = self.message
        payload.update(self.details)
        return payload


class StudioBadRequestError(StudioError):
    """Error when the input value is invalid."""


class StudioNotFoundError(StudioError):
    """Error when the target resource is not found."""


class StudioConflictError(StudioError):
    """Error when a conflict occurs."""


class StudioUnprocessableEntityError(StudioError):
    """Error when the syntax is correct but processing is not possible."""


class StudioPort(ABC):
    """Input boundary for Workflow Studio."""

    @abstractmethod
    def get_studio_target(self) -> dict[str, Any]:
        """Returns the current Studio target information."""

    @abstractmethod
    def get_studio_files(self) -> dict[str, Any]:
        """Returns a list of workflow / YAML candidates under the workspace."""

    @abstractmethod
    def read_studio_yaml_file(self, body: dict[str, Any]) -> dict[str, Any]:
        """Returns the YAML file contents under the workspace."""

    @abstractmethod
    def save_studio_yaml_file(self, body: dict[str, Any]) -> dict[str, Any]:
        """Creates or updates a YAML file under the workspace."""

    @abstractmethod
    def open_studio_target(self, body: dict[str, Any]) -> dict[str, Any]:
        """Opens an existing workflow as a Studio target."""

    @abstractmethod
    def create_studio_target(self, body: dict[str, Any]) -> dict[str, Any]:
        """Creates a new workflow and opens it as a Studio target."""

    @abstractmethod
    def get_workflow(self) -> dict[str, Any]:
        """Returns the current workflow and UI state."""

    @abstractmethod
    def get_form(self) -> dict[str, Any]:
        """Returns workflow display information for form editing."""

    @abstractmethod
    def diff(self, body: dict[str, Any]) -> dict[str, Any]:
        """Returns the diff of the editing proposal."""

    @abstractmethod
    def form_preview(self, body: dict[str, Any]) -> dict[str, Any]:
        """Returns a diff preview from form editing input."""

    @abstractmethod
    def catalog_preview(self, body: dict[str, Any]) -> dict[str, Any]:
        """Returns a Catalog configuration preview."""

    @abstractmethod
    def save(self, body: dict[str, Any]) -> dict[str, Any]:
        """Saves the editing proposal."""

    @abstractmethod
    def rollback(self, body: dict[str, Any]) -> dict[str, Any]:
        """Restores using the specified backup ID."""
