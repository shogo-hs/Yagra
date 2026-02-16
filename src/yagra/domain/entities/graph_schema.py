"""Defines the base schema for Yagra YAML."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NodeSpec(BaseModel):
    """Represents a node definition in the graph."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    handler: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class EdgeSpec(BaseModel):
    """Represents an edge definition for transitions between nodes."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    condition: str | None = None


class GraphSpec(BaseModel):
    """Represents the complete Yagra YAML definition."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1)
    start_at: str = Field(min_length=1)
    end_at: list[str] = Field(min_length=1)
    nodes: list[NodeSpec] = Field(min_length=1)
    edges: list[EdgeSpec] = Field(min_length=0)
    params: dict[str, Any] = Field(default_factory=dict)
