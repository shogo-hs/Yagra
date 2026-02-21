"""Entity definitions for the Yagra YAML schema."""

from yagra.domain.entities.comparison import (
    ComparisonStrategy,
    compare_exact,
    compare_snapshots,
    compare_structural,
)
from yagra.domain.entities.cost_table import (
    LLM_PRICING_TABLE,
    ModelPricing,
    estimate_cost,
)
from yagra.domain.entities.golden_case import (
    LLM_HANDLER_NAMES,
    GoldenCase,
    GoldenTestResult,
    NodeComparisonResult,
    NodeSnapshot,
)
from yagra.domain.entities.graph_schema import (
    EdgeSpec,
    FanOutSpec,
    GraphSpec,
    NodeSpec,
    StateFieldSpec,
)
from yagra.domain.entities.trace import (
    ErrorTrace,
    LLMCallTrace,
    NodeStatus,
    NodeTrace,
    RunSummary,
    WorkflowRunTrace,
)

__all__ = [
    # comparison
    "ComparisonStrategy",
    "compare_exact",
    "compare_snapshots",
    "compare_structural",
    # cost_table
    "LLM_PRICING_TABLE",
    "ModelPricing",
    "estimate_cost",
    # golden_case
    "LLM_HANDLER_NAMES",
    "GoldenCase",
    "GoldenTestResult",
    "NodeComparisonResult",
    "NodeSnapshot",
    # graph_schema
    "EdgeSpec",
    "FanOutSpec",
    "GraphSpec",
    "NodeSpec",
    "StateFieldSpec",
    # trace
    "ErrorTrace",
    "LLMCallTrace",
    "NodeStatus",
    "NodeTrace",
    "RunSummary",
    "WorkflowRunTrace",
]
