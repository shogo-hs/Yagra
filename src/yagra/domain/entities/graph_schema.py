"""Defines the base schema for Yagra YAML."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RetrySpec(BaseModel):
    """Retry configuration for a node.

    When specified on a node, the node handler is wrapped with retry logic.
    On failure, the handler is re-invoked up to ``max_attempts`` times with
    the configured backoff strategy.
    """

    model_config = ConfigDict(extra="forbid")

    max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description=(
            "Maximum number of attempts including the first try. "
            "Must be between 1 and 10."
        ),
        examples=[3, 5],
    )
    backoff: Literal["exponential", "fixed"] = Field(
        default="exponential",
        description=(
            "Backoff strategy between retries. "
            "'exponential': delay = base_delay_seconds * 2^attempt. "
            "'fixed': delay = base_delay_seconds."
        ),
        examples=["exponential", "fixed"],
    )
    base_delay_seconds: float = Field(
        default=2.0,
        ge=0.0,
        le=60.0,
        description="Base delay in seconds between retries.",
        examples=[1.0, 2.0, 5.0],
    )


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
    retry: RetrySpec | None = Field(
        default=None,
        description=(
            "Retry configuration. When specified, the node handler is wrapped "
            "with retry logic using the given backoff strategy. If omitted, "
            "uses the handler's built-in defaults (e.g. llm handler retries 3 times)."
        ),
        examples=[None, {"max_attempts": 3, "backoff": "exponential", "base_delay_seconds": 2}],
    )
    timeout_seconds: int | None = Field(
        default=None,
        ge=1,
        le=600,
        description=(
            "Maximum execution time in seconds for this node. "
            "If the handler does not complete within this time, a TimeoutError is raised. "
            "If omitted, uses the handler's built-in default."
        ),
        examples=[None, 30, 60, 120],
    )
    fallback: str | None = Field(
        default=None,
        description=(
            "Node ID to route to when this node fails after all retries are exhausted. "
            "Must reference a valid node ID in the workflow. "
            "On failure, state['__error__'] is set with the error message."
        ),
        examples=[None, "fallback_handler"],
    )


class FanOutSpec(BaseModel):
    """Configuration for Send API fan-out pattern.

    When specified on an edge, the source node's output state is used to
    dispatch multiple parallel executions of the target node via LangGraph's
    Send API. Each item in the list at ``items_key`` gets its own Send instance.
    """

    model_config = ConfigDict(extra="forbid")

    items_key: str = Field(
        min_length=1,
        description=(
            "Key in the state that holds the list of items to fan out over. "
            "Each element in state[items_key] will be dispatched as a separate Send."
        ),
        examples=["topics", "tasks", "items"],
    )
    item_key: str = Field(
        min_length=1,
        description=(
            "Key name used when passing each item to the target node via Send. "
            "The target node will receive {'item_key': item} in its state."
        ),
        examples=["topic", "task", "item"],
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
    fan_out: FanOutSpec | None = Field(
        default=None,
        description=(
            "Fan-out configuration for Send API parallel dispatch. "
            "When specified, the edge becomes a fan-out edge that dispatches "
            "each item in state[fan_out.items_key] to the target node as a separate "
            "parallel execution. Requires the target's output key to use 'reducer: add' "
            "in state_schema to collect results. "
            "Cannot be combined with 'condition'."
        ),
        examples=[
            None,
            {"items_key": "topics", "item_key": "topic"},
        ],
    )

    def model_post_init(self, __context: Any) -> None:
        """Validates edge consistency after model initialization.

        Args:
            __context: Pydantic context (unused).

        Raises:
            ValueError: If condition and fan_out are both specified.
        """
        if self.condition is not None and self.fan_out is not None:
            raise ValueError(
                "EdgeSpec: 'condition' and 'fan_out' cannot both be specified on the same edge"
            )


# Supported state field types
STATE_FIELD_TYPES = frozenset({"str", "int", "float", "bool", "list", "dict", "messages"})

# Supported reducer types for state fields
REDUCER_TYPES = frozenset({"add"})


class StateFieldSpec(BaseModel):
    """Represents a single field definition in state_schema.

    Each field specifies the type and optional reducer of the state key.
    Use 'messages' to enable LangGraph's add_messages reducer for chat history.
    Use 'reducer: add' with list fields to enable operator.add reducer for fan-in
    from parallel nodes (Send API / fan-out patterns).
    """

    model_config = ConfigDict(extra="forbid")

    type: str = Field(
        description=(
            "Type of the state field. "
            "Supported values: str, int, float, bool, list, dict, messages. "
            "'messages' enables LangGraph's add_messages reducer for chat history."
        ),
        examples=["str", "int", "messages"],
    )
    reducer: str | None = Field(
        default=None,
        description=(
            "Reducer function for merging parallel state updates. "
            "Supported values: 'add' (operator.add, appends list results from parallel nodes). "
            "Only valid with type 'list'. "
            "Required when multiple parallel nodes write to the same list key (fan-in pattern). "
            "If omitted, the last writer wins (standard behavior)."
        ),
        examples=["add", None],
    )

    @classmethod
    def validate_type(cls, value: str) -> str:
        """Validates that the type is a supported state field type.

        Args:
            value: Type string to validate.

        Returns:
            The validated type string.

        Raises:
            ValueError: If the type is not supported.
        """
        if value not in STATE_FIELD_TYPES:
            supported = ", ".join(sorted(STATE_FIELD_TYPES))
            raise ValueError(
                f"unsupported state field type: '{value}'. Supported types: {supported}"
            )
        return value

    def model_post_init(self, __context: Any) -> None:
        """Validates field consistency after model initialization.

        Args:
            __context: Pydantic context (unused).

        Raises:
            ValueError: If type or reducer is invalid, or combination is inconsistent.
        """
        self.validate_type(self.type)
        if self.reducer is not None:
            if self.reducer not in REDUCER_TYPES:
                supported = ", ".join(sorted(REDUCER_TYPES))
                raise ValueError(
                    f"unsupported reducer: '{self.reducer}'. Supported reducers: {supported}"
                )
            if self.reducer == "add" and self.type not in ("list", "messages"):
                raise ValueError(
                    f"reducer 'add' is only valid with type 'list' or 'messages', "
                    f"but got type '{self.type}'"
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
    state_schema: dict[str, StateFieldSpec] = Field(
        default_factory=dict,
        description=(
            "State schema definition. Specifies the type and reducer for each state key. "
            "If omitted, defaults to dict (plain key-value state). "
            "Use 'type: messages' to enable LangGraph MessagesState with add_messages reducer for chat history. "
            "Supported types: str, int, float, bool, list, dict, messages."
        ),
        examples=[
            {},
            {
                "messages": {"type": "messages"},
                "result": {"type": "str"},
            },
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
