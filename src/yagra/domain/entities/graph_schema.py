"""Defines the base schema for Yagra YAML."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NodeSpec(BaseModel):
    """Represents a node definition in the graph."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        min_length=1,
        description="Unique identifier for the node. Referenced by edges source/target and start_at/end_at. Alphanumerics and underscores are recommended.",
        examples=["translate", "summarize", "classify"],
    )
    handler: str = Field(
        min_length=1,
        description="Name of the handler to execute at this node. Built-in handlers: 'llm' (text output), 'structured_llm' (Pydantic structured output), 'streaming_llm' (streaming output). Custom handlers use the name registered in the Registry.",
        examples=["llm", "structured_llm", "streaming_llm", "my_custom_handler"],
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameter dictionary passed to the handler. llm handler: prompt_ref or prompt (required), model (required), output_key (defaults to 'output'). structured_llm handler: same as above plus schema_yaml ('name: str\\nage: int' format). streaming_llm handler: same as above plus stream (bool, default true).",
        examples=[
            {
                "prompt_ref": "prompts/translate.txt",
                "model": "gpt-4o-mini",
                "output_key": "translation",
            },
            {
                "prompt": {"role": "user", "content": "Please summarize: {text}"},
                "model": "gpt-4o-mini",
            },
        ],
    )


class EdgeSpec(BaseModel):
    """Represents an edge definition for transitions between nodes."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(
        min_length=1,
        description="ID of the source node. Must be a node ID present in the nodes list.",
        examples=["translate", "classify"],
    )
    target: str = Field(
        min_length=1,
        description="ID of the target node. Must be a node ID present in the nodes list. Transitions always go to this node when there is no conditional branch (no condition).",
        examples=["summarize", "END"],
    )
    condition: str | None = Field(
        default=None,
        description="Condition for conditional branching. A string compared against state['__next__'], or a condition function name. Omit for unconditional transitions.",
        examples=["approve", "reject", None],
    )


class GraphSpec(BaseModel):
    """Represents the complete Yagra YAML definition."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(
        min_length=1,
        description="Version of the YAML schema. Specify '1.0' currently.",
        examples=["1.0"],
    )
    start_at: str = Field(
        min_length=1,
        description="ID of the node to execute first when the workflow starts. Must be one of the IDs in the nodes list.",
        examples=["translate", "input_node"],
    )
    end_at: list[str] = Field(
        min_length=1,
        description="List of terminal node IDs. The workflow ends when any of these nodes completes. Multiple IDs can be specified.",
        examples=[["translate"], ["approve", "reject"]],
    )
    nodes: list[NodeSpec] = Field(
        min_length=1,
        description="List of node definitions comprising the workflow. Each node has id, handler, and params.",
        examples=[
            [
                {
                    "id": "translate",
                    "handler": "llm",
                    "params": {"prompt_ref": "prompts/translate.txt", "model": "gpt-4o-mini"},
                }
            ]
        ],
    )
    edges: list[EdgeSpec] = Field(
        min_length=0,
        description="List of transition definitions between nodes. Enumerates edges from source to target. Conditional branching is specified with the condition field.",
        examples=[
            [
                {"source": "classify", "target": "approve", "condition": "approved"},
                {"source": "classify", "target": "reject", "condition": "rejected"},
            ]
        ],
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Workflow-level global parameters. Currently unused but reserved for future extensions.",
        examples=[{}],
    )
    interrupt_before: list[str] = Field(
        default_factory=list,
        description="List of node IDs whose execution should be interrupted before they run. Used for HITL (Human-in-the-Loop) to insert human review/approval. Resume with `Yagra.resume()`.",
        examples=[["review_node"], []],
    )
    interrupt_after: list[str] = Field(
        default_factory=list,
        description="List of node IDs whose execution should be interrupted after they run. Used for HITL (Human-in-the-Loop) to allow humans to review/modify output. Resume with `Yagra.resume()`.",
        examples=[["generate_node"], []],
    )
