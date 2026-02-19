"""Loads workflow.yaml and converts it to a GraphSpec."""

from __future__ import annotations

from os import PathLike

from yagra.application.use_cases.workflow_validation_reporter import load_validated_graph_spec
from yagra.domain.entities import GraphSpec


def load_graph_spec_from_workflow(
    workflow_path: str | PathLike[str],
    bundle_root: str | PathLike[str] | None = None,
) -> GraphSpec:
    """Loads a workflow file and returns a reference-resolved `GraphSpec`.

    Args:
        workflow_path: Path to the entry workflow YAML.
        bundle_root: Base directory for split references. Defaults to workflow parent directory.

    Returns:
        Reference-resolved and schema-validated `GraphSpec`.

    Raises:
        WorkflowValidationFailedError: If workflow validation fails.
    """
    return load_validated_graph_spec(workflow_path=workflow_path, bundle_root=bundle_root)
