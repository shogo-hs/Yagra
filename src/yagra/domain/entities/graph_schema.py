"""Yagra YAML の基本スキーマを定義する。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NodeSpec(BaseModel):
    """グラフ内ノードの定義を表すモデル。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    handler: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class EdgeSpec(BaseModel):
    """ノード間の遷移定義を表すモデル。"""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    condition: str | None = None


class GraphSpec(BaseModel):
    """Yagra 全体の YAML 定義を表すモデル。"""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1)
    start_at: str = Field(min_length=1)
    end_at: list[str] = Field(min_length=1)
    nodes: list[NodeSpec] = Field(min_length=1)
    edges: list[EdgeSpec] = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
