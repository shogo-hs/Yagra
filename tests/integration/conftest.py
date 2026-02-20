"""Shared fixtures for Studio integration tests."""

from __future__ import annotations

import textwrap
from pathlib import Path
from threading import Thread
from typing import TYPE_CHECKING, Any

import pytest
import yaml

from yagra.adapters.inbound import create_workflow_studio_server

if TYPE_CHECKING:
    from playwright.sync_api import Page


# ---------------------------------------------------------------------------
# Helpers (duplicated from test_workflow_studio_api for isolation)
# ---------------------------------------------------------------------------


def _write_workflow(path: Path, payload: dict[str, Any]) -> Path:
    """Write a workflow YAML file, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def _minimal_workflow() -> dict[str, Any]:
    """Returns a minimal valid workflow payload."""
    return {
        "version": "1.0",
        "start_at": "step_a",
        "end_at": ["step_a"],
        "nodes": [{"id": "step_a", "handler": "llm", "params": {"prompt_ref": "prompts/my_prompts.yaml#step_a"}}],
        "edges": [],
        "params": {},
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def studio_workspace(tmp_path: Path) -> Path:
    """Creates a workspace with a workflow in a *subdirectory* (bdi_workflow/).

    Layout::

        tmp_path/
          workspace/
            sub_workflow/
              workflow.yaml        ← target workflow
              prompts/
                my_prompts.yaml    ← prompt file
    """
    workspace = tmp_path / "workspace"

    # Workflow lives in a subdirectory, not at the workspace root.
    workflow_path = workspace / "sub_workflow" / "workflow.yaml"
    _write_workflow(workflow_path, _minimal_workflow())

    # Prompt file alongside the workflow.
    prompts_path = workspace / "sub_workflow" / "prompts" / "my_prompts.yaml"
    prompts_path.parent.mkdir(parents=True, exist_ok=True)
    prompts_path.write_text(
        textwrap.dedent("""\
            step_a:
              system: You are a helpful assistant.
              user: "Hello: {{ query }}"
        """),
        encoding="utf-8",
    )

    return workspace


@pytest.fixture()
def studio_server(studio_workspace: Path):
    """Starts a Studio HTTP server and yields (server, base_url, workflow_path)."""
    workflow_path = studio_workspace / "sub_workflow" / "workflow.yaml"

    server = create_workflow_studio_server(
        workspace_root=studio_workspace,
        workflow_path=str(workflow_path),
        backup_dir=studio_workspace / ".yagra-backups",
        host="127.0.0.1",
        port=0,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    address = server.server_address
    host = address[0].decode("utf-8") if isinstance(address[0], bytes) else str(address[0])
    base_url = f"http://{host}:{address[1]}"

    yield server, base_url, workflow_path

    server.shutdown()


@pytest.fixture()
def studio_utils_page(page: "Page", studio_server):
    """Opens the Studio page with ?__test_utils=1 and waits for Vue to mount.

    Returns (page, base_url) so tests can call page.evaluate("__studioUtils.*").
    """
    _, base_url, _ = studio_server

    # Load page with test-utils flag so window.__studioUtils is exposed.
    page.goto(f"{base_url}/?__test_utils=1")

    # Wait until Vue has mounted and exposed the utilities.
    page.wait_for_function("() => typeof window.__studioUtils !== 'undefined'", timeout=10_000)

    return page, base_url
