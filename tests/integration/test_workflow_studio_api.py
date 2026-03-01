from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from threading import Thread
from typing import Any
from urllib import error, request

import yaml

from yagra.adapters.inbound import create_workflow_studio_server


def _base_payload() -> dict[str, Any]:
    return {
        "version": "1.0",
        "start_at": "router",
        "end_at": ["finish"],
        "nodes": [
            {"id": "router", "handler": "router_handler"},
            {"id": "planner", "handler": "planner_handler"},
            {"id": "finish", "handler": "finish_handler"},
        ],
        "edges": [
            {"source": "router", "target": "planner", "condition": "needs_plan"},
            {"source": "router", "target": "finish", "condition": "direct_answer"},
            {"source": "planner", "target": "finish"},
        ],
        "params": {},
    }


def _write_workflow(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def _request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    headers: dict[str, str] = {}
    data: bytes | None = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=5) as res:
            body = json.loads(res.read().decode("utf-8"))
            return res.status, body
    except error.HTTPError as exc:
        body = json.loads(exc.read().decode("utf-8"))
        return exc.code, body


def _server_base_url(server: Any) -> str:
    """Constructs the base URL of the test server.

    Args:
        server: A `ThreadingHTTPServer`-compatible object.

    Returns:
        The base URL string.
    """
    address = server.server_address
    raw_host = address[0]
    host = raw_host.decode("utf-8") if isinstance(raw_host, bytes) else str(raw_host)
    port = int(address[1])
    return f"http://{host}:{port}"


def test_workflow_studio_api_launcher_open_and_create(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    existing_workflow = _write_workflow(
        workspace_root / "workflows" / "existing.yaml",
        _base_payload(),
    )

    server = create_workflow_studio_server(
        workspace_root=workspace_root,
        backup_dir=tmp_path / ".yagra-backups",
        host="127.0.0.1",
        port=0,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = _server_base_url(server)

    try:
        status, target_payload = _request_json("GET", f"{base_url}/api/studio/target")
        assert status == 200
        assert target_payload["has_target"] is False
        assert target_payload["workflow_path"] is None
        assert target_payload["workspace_root"] == str(workspace_root.resolve())

        status, files_payload = _request_json("GET", f"{base_url}/api/studio/files")
        assert status == 200
        assert "workflows/existing.yaml" in files_payload["workflows"]

        status, form_payload = _request_json("GET", f"{base_url}/api/workflow/form")
        assert status == 409
        assert form_payload["error"] == "studio_target_required"

        status, create_payload = _request_json(
            "POST",
            f"{base_url}/api/studio/create",
            {"workflow_path": "workflows/new.yaml"},
        )
        assert status == 200
        created_workflow = workspace_root / "workflows" / "new.yaml"
        assert created_workflow.exists()
        assert created_workflow.with_suffix(".workflow-ui.json").exists()
        assert create_payload["workflow_path"] == str(created_workflow.resolve())

        status, created_form_payload = _request_json("GET", f"{base_url}/api/workflow/form")
        assert status == 200
        assert created_form_payload["workflow"]["start_at"] == "start"
        assert created_form_payload["workflow"]["end_at"] == ["end"]

        status, open_payload = _request_json(
            "POST",
            f"{base_url}/api/studio/open",
            {"workflow_path": "workflows/existing.yaml"},
        )
        assert status == 200
        assert open_payload["workflow_path"] == str(existing_workflow.resolve())

        status, opened_form_payload = _request_json("GET", f"{base_url}/api/workflow/form")
        assert status == 200
        assert opened_form_payload["workflow"]["start_at"] == "router"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_workflow_studio_api_defaults_workspace_root_to_cwd_for_nested_workflow(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workflow_path = _write_workflow(workspace_root / "workflows" / "main.yaml", _base_payload())
    previous_cwd = Path.cwd()
    os.chdir(workspace_root)
    try:
        server = create_workflow_studio_server(
            workflow_path=workflow_path,
            backup_dir=tmp_path / ".yagra-backups",
            host="127.0.0.1",
            port=0,
        )
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = _server_base_url(server)

        try:
            status, target_payload = _request_json("GET", f"{base_url}/api/studio/target")
            assert status == 200
            assert target_payload["has_target"] is True
            assert target_payload["workspace_root"] == str(workspace_root.resolve())

            status, files_payload = _request_json("GET", f"{base_url}/api/studio/files")
            assert status == 200
            assert "workflows/main.yaml" in files_payload["workflows"]
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
    finally:
        os.chdir(previous_cwd)


def test_workflow_studio_html_bootstrap_has_valid_backslash_normalization_js(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    _write_workflow(workspace_root / "workflows" / "existing.yaml", _base_payload())

    server = create_workflow_studio_server(
        workspace_root=workspace_root,
        backup_dir=tmp_path / ".yagra-backups",
        host="127.0.0.1",
        port=0,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = _server_base_url(server)

    try:
        req = request.Request(url=f"{base_url}/", method="GET")
        with request.urlopen(req, timeout=5) as res:
            html = res.read().decode("utf-8")
        assert 'text.replace(/\\\\/g, "/")' in html
        assert 'return "prompts";' in html
        assert "const studioFilesRequestSeq = ref(0);" in html
        assert "const requestSeq = studioFilesRequestSeq.value + 1;" in html
        assert "if (requestSeq !== studioFilesRequestSeq.value) {" in html
        assert "if (currentYamlPath && !yamlFiles.value.includes(currentYamlPath)) {" not in html
        assert "https://cdn.jsdelivr.net" not in html
        assert "/assets/vendor/vue/3.5.28/vue.esm-browser.prod.js" in html
        assert "/assets/vendor/vue-flow/core/1.48.2/style.css" in html

        asset_req = request.Request(
            url=f"{base_url}/assets/vendor/vue/3.5.28/vue.esm-browser.prod.js",
            method="GET",
        )
        with request.urlopen(asset_req, timeout=5) as asset_res:
            asset_js = asset_res.read().decode("utf-8")
            assert asset_res.status == 200
            assert "createApp" in asset_js

        status, payload = _request_json(
            "GET",
            f"{base_url}/assets/%2e%2e/pyproject.toml",
        )
        assert status == 404
        assert payload["error"] == "not_found"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_workflow_studio_api_supports_prompt_yaml_read_and_save(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    _write_workflow(workspace_root / "workflows" / "main.yaml", _base_payload())

    server = create_workflow_studio_server(
        workspace_root=workspace_root,
        backup_dir=tmp_path / ".yagra-backups",
        host="127.0.0.1",
        port=0,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = _server_base_url(server)

    try:
        status, save_payload = _request_json(
            "POST",
            f"{base_url}/api/studio/file/save",
            {
                "path": "prompts/new_task.yaml",
                "content": "intent:\n  system: classify\n  user: '{{input}}'\n",
                "overwrite": False,
            },
        )
        assert status == 200
        assert save_payload["path"] == "prompts/new_task.yaml"
        assert (workspace_root / "prompts" / "new_task.yaml").exists()

        status, read_payload = _request_json(
            "POST",
            f"{base_url}/api/studio/file/read",
            {"path": "prompts/new_task.yaml"},
        )
        assert status == 200
        assert read_payload["path"] == "prompts/new_task.yaml"
        assert "intent" in read_payload["content"]
        assert "intent" in read_payload["key_paths"]
        assert read_payload["prompt_entries"] == [
            {
                "key_path": "intent",
                "system": "classify",
                "user": "{{input}}",
            }
        ]

        status, files_payload = _request_json("GET", f"{base_url}/api/studio/files")
        assert status == 200
        assert "prompts/new_task.yaml" in files_payload["yaml_files"]

        status, conflict_payload = _request_json(
            "POST",
            f"{base_url}/api/studio/file/save",
            {
                "path": "prompts/new_task.yaml",
                "content": "intent:\n  system: classify\n",
                "overwrite": False,
            },
        )
        assert status == 409
        assert conflict_payload["error"] == "yaml_file_exists"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_workflow_studio_api_save_accepts_path_based_prompt_ref(tmp_path: Path) -> None:
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", _base_payload())
    prompt_file_path = tmp_path / "prompts.yaml"
    prompt_file_path.write_text(
        yaml.safe_dump(
            {
                "planning": {
                    "special": {
                        "system": "You are planner.",
                    }
                }
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    backup_dir = tmp_path / ".yagra-backups"

    server = create_workflow_studio_server(
        workflow_path=workflow_path,
        backup_dir=backup_dir,
        host="127.0.0.1",
        port=0,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = _server_base_url(server)

    try:
        status, form_payload = _request_json("GET", f"{base_url}/api/workflow/form")
        assert status == 200
        base_revision = str(form_payload["revision"])
        candidate_workflow = deepcopy(form_payload["workflow"])
        candidate_workflow["params"] = {}
        candidate_workflow["nodes"][1]["params"] = {
            "prompt_ref": f"{prompt_file_path.resolve()}#planning.special",
            "model": {
                "provider": "openai",
                "name": "gpt-4.1-mini",
                "temperature": 0.35,
            },
        }

        status, save_payload = _request_json(
            "POST",
            f"{base_url}/api/workflow/save",
            {
                "workflow": candidate_workflow,
                "ui_state": form_payload["ui_state"],
                "base_revision": base_revision,
            },
        )
        assert status == 200
        assert save_payload["backup_id"]

        status, after_form = _request_json("GET", f"{base_url}/api/workflow/form")
        assert status == 200
        assert after_form["workflow"]["nodes"][1]["params"]["prompt_ref"] == (
            f"{prompt_file_path.resolve()}#planning.special"
        )
        assert after_form["workflow"]["nodes"][1]["params"]["model"]["temperature"] == 0.35
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_workflow_studio_api_resolves_prompt_ref_from_workspace_root_by_default(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workflow_path = _write_workflow(workspace_root / "workflows" / "main.yaml", _base_payload())
    (workspace_root / "prompts").mkdir(parents=True, exist_ok=True)
    (workspace_root / "prompts" / "catalog.yaml").write_text(
        yaml.safe_dump(
            {
                "intent": {
                    "system": "Classify the request.",
                    "user": "{{input}}",
                }
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    previous_cwd = Path.cwd()
    os.chdir(workspace_root)
    try:
        server = create_workflow_studio_server(
            workflow_path=workflow_path,
            backup_dir=tmp_path / ".yagra-backups",
            host="127.0.0.1",
            port=0,
        )
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = _server_base_url(server)

        try:
            status, form_payload = _request_json("GET", f"{base_url}/api/workflow/form")
            assert status == 200
            base_revision = str(form_payload["revision"])
            candidate_workflow = deepcopy(form_payload["workflow"])
            candidate_workflow["nodes"][1]["params"] = {
                "prompt_ref": "prompts/catalog.yaml#intent",
                "model": {
                    "provider": "openai",
                    "name": "gpt-4.1-mini",
                },
            }

            status, save_payload = _request_json(
                "POST",
                f"{base_url}/api/workflow/save",
                {
                    "workflow": candidate_workflow,
                    "ui_state": form_payload["ui_state"],
                    "base_revision": base_revision,
                },
            )
            assert status == 200
            assert save_payload["backup_id"]
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
    finally:
        os.chdir(previous_cwd)


def test_workflow_studio_api_supports_diff_save_rollback(tmp_path: Path) -> None:
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", _base_payload())
    backup_dir = tmp_path / ".yagra-backups"

    server = create_workflow_studio_server(
        workflow_path=workflow_path,
        backup_dir=backup_dir,
        host="127.0.0.1",
        port=0,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = _server_base_url(server)

    try:
        status, current = _request_json("GET", f"{base_url}/api/workflow")
        assert status == 200
        base_revision = str(current["revision"])
        assert current["validation_report"]["is_valid"] is True

        candidate_workflow = deepcopy(current["workflow"])
        candidate_workflow["params"] = {"temperature": 0.1}
        candidate_ui_state = {
            "positions": {"router": {"x": 150, "y": 200}},
            "edge_handles": {"0": {"source_handle": "bottom-out", "target_handle": "top-in"}},
        }

        status, diff_response = _request_json(
            "POST",
            f"{base_url}/api/workflow/diff",
            {
                "workflow": candidate_workflow,
                "ui_state": candidate_ui_state,
                "base_revision": base_revision,
            },
        )
        assert status == 200
        assert diff_response["summary"]["total"] >= 1
        assert diff_response["validation_report"]["is_valid"] is True

        status, save_response = _request_json(
            "POST",
            f"{base_url}/api/workflow/save",
            {
                "workflow": candidate_workflow,
                "ui_state": candidate_ui_state,
                "base_revision": base_revision,
            },
        )
        assert status == 200
        assert save_response["backup_id"]
        saved_revision = str(save_response["saved_revision"])
        assert saved_revision != base_revision

        status, after_save = _request_json("GET", f"{base_url}/api/workflow")
        assert status == 200
        assert after_save["ui_state"]["positions"]["router"]["x"] == 150
        assert after_save["ui_state"]["edge_handles"]["0"]["source_handle"] == "bottom-out"
        assert after_save["ui_state"]["edge_handles"]["0"]["target_handle"] == "top-in"

        status, rollback_response = _request_json(
            "POST",
            f"{base_url}/api/workflow/rollback",
            {"backup_id": save_response["backup_id"]},
        )
        assert status == 200
        assert rollback_response["restored_revision"] == base_revision
        safety_backup_id = str(rollback_response["safety_backup_id"])
        assert safety_backup_id

        status, after = _request_json("GET", f"{base_url}/api/workflow")
        assert status == 200
        assert after["revision"] == base_revision
        assert after["workflow"]["params"] == {}

        status, restore_latest_response = _request_json(
            "POST",
            f"{base_url}/api/workflow/rollback",
            {"backup_id": safety_backup_id},
        )
        assert status == 200
        assert restore_latest_response["restored_revision"] == saved_revision

        status, restored_latest = _request_json("GET", f"{base_url}/api/workflow")
        assert status == 200
        assert restored_latest["revision"] == saved_revision
        assert restored_latest["workflow"]["params"]["temperature"] == 0.1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_workflow_studio_api_returns_conflict_for_stale_revision(tmp_path: Path) -> None:
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", _base_payload())

    server = create_workflow_studio_server(
        workflow_path=workflow_path,
        backup_dir=tmp_path / ".yagra-backups",
        host="127.0.0.1",
        port=0,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = _server_base_url(server)

    try:
        status, current = _request_json("GET", f"{base_url}/api/workflow")
        assert status == 200
        latest_revision = str(current["revision"])

        candidate_workflow = deepcopy(current["workflow"])
        candidate_workflow["params"] = {"temperature": 0.1}
        status, _ = _request_json(
            "POST",
            f"{base_url}/api/workflow/save",
            {
                "workflow": candidate_workflow,
                "ui_state": {},
                "base_revision": latest_revision,
            },
        )
        assert status == 200

        stale_candidate = deepcopy(candidate_workflow)
        stale_candidate["params"] = {"temperature": 0.2}
        status, response = _request_json(
            "POST",
            f"{base_url}/api/workflow/diff",
            {
                "workflow": stale_candidate,
                "ui_state": {},
                "base_revision": latest_revision,
            },
        )
        assert status == 409
        assert response["error"] == "revision_conflict"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_workflow_studio_api_supports_bootstrap_save_from_empty_workflow(
    tmp_path: Path,
) -> None:
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", {})
    backup_dir = tmp_path / ".yagra-backups"

    server = create_workflow_studio_server(
        workflow_path=workflow_path,
        backup_dir=backup_dir,
        host="127.0.0.1",
        port=0,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = _server_base_url(server)

    try:
        status, form_payload = _request_json("GET", f"{base_url}/api/workflow/form")
        assert status == 200
        assert form_payload["nodes"] == []
        assert form_payload["edges"] == []
        base_revision = str(form_payload["revision"])

        candidate_workflow = {
            "version": "1.0",
            "start_at": "start",
            "end_at": ["finish"],
            "nodes": [
                {"id": "start", "handler": "start_handler"},
                {"id": "finish", "handler": "finish_handler"},
            ],
            "edges": [{"source": "start", "target": "finish"}],
            "params": {},
        }
        candidate_ui_state = {
            "positions": {
                "start": {"x": 80, "y": 120},
                "finish": {"x": 350, "y": 120},
            }
        }
        status, save_payload = _request_json(
            "POST",
            f"{base_url}/api/workflow/save",
            {
                "workflow": candidate_workflow,
                "ui_state": candidate_ui_state,
                "base_revision": base_revision,
            },
        )
        assert status == 200
        assert save_payload["backup_id"]

        status, after_form = _request_json("GET", f"{base_url}/api/workflow/form")
        assert status == 200
        assert after_form["workflow"]["version"] == "1.0"
        assert after_form["workflow"]["start_at"] == "start"
        assert after_form["workflow"]["end_at"] == ["finish"]
        assert len(after_form["nodes"]) == 2
        assert len(after_form["edges"]) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_workflow_studio_form_preview_and_save(tmp_path: Path) -> None:
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", _base_payload())
    prompt_file_path = tmp_path / "prompts.yaml"
    prompt_file_path.write_text(
        yaml.safe_dump(
            {"edited": {"system": "edited prompt", "user": "do something"}},
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    backup_dir = tmp_path / ".yagra-backups"

    server = create_workflow_studio_server(
        workflow_path=workflow_path,
        backup_dir=backup_dir,
        host="127.0.0.1",
        port=0,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = _server_base_url(server)

    try:
        status, form_payload = _request_json("GET", f"{base_url}/api/workflow/form")
        assert status == 200
        base_revision = str(form_payload["revision"])
        assert len(form_payload["nodes"]) == 3
        assert len(form_payload["edges"]) == 3

        status, preview = _request_json(
            "POST",
            f"{base_url}/api/workflow/form/preview",
            {
                "base_revision": base_revision,
                "node_creates": [],
                "node_edits": [
                    {
                        "node_id": "planner",
                        "prompt_ref": f"{prompt_file_path.resolve()}#edited",
                        "model": {"provider": "openai", "name": "gpt-4.1-nano"},
                    }
                ],
                "edge_creates": [],
                "edge_rewires": [],
                "edge_edits": [{"edge_index": 2, "condition": "done"}],
                "ui_state": {},
            },
        )
        assert status == 200
        assert preview["summary"]["total"] >= 1
        assert preview["validation_report"]["is_valid"] is True
        assert (
            preview["candidate_workflow"]["nodes"][1]["params"]["prompt_ref"]
            == f"{prompt_file_path.resolve()}#edited"
        )
        assert preview["candidate_workflow"]["edges"][2]["condition"] == "done"

        status, save_payload = _request_json(
            "POST",
            f"{base_url}/api/workflow/save",
            {
                "workflow": preview["candidate_workflow"],
                "ui_state": preview["candidate_ui_state"],
                "base_revision": base_revision,
            },
        )
        assert status == 200
        assert save_payload["backup_id"]

        status, after_form = _request_json("GET", f"{base_url}/api/workflow/form")
        assert status == 200
        planner = next(item for item in after_form["nodes"] if item["id"] == "planner")
        assert planner["prompt_ref"] == f"{prompt_file_path.resolve()}#edited"
        assert planner["model"]["name"] == "gpt-4.1-nano"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_workflow_studio_form_preview_rejects_missing_required_fields(
    tmp_path: Path,
) -> None:
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", _base_payload())
    backup_dir = tmp_path / ".yagra-backups"

    server = create_workflow_studio_server(
        workflow_path=workflow_path,
        backup_dir=backup_dir,
        host="127.0.0.1",
        port=0,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = _server_base_url(server)

    try:
        status, form_payload = _request_json("GET", f"{base_url}/api/workflow/form")
        assert status == 200
        base_revision = str(form_payload["revision"])

        status, response = _request_json(
            "POST",
            f"{base_url}/api/workflow/form/preview",
            {
                "base_revision": base_revision,
                "node_edits": [],
                "edge_creates": [],
                "edge_rewires": [],
                "edge_edits": [],
                "ui_state": {},
            },
        )
        assert status == 400
        assert response["error"] == "node_creates must be an array"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_workflow_studio_form_preview_supports_dnd_like_edits(tmp_path: Path) -> None:
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", _base_payload())
    backup_dir = tmp_path / ".yagra-backups"

    server = create_workflow_studio_server(
        workflow_path=workflow_path,
        backup_dir=backup_dir,
        host="127.0.0.1",
        port=0,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = _server_base_url(server)

    try:
        status, form_payload = _request_json("GET", f"{base_url}/api/workflow/form")
        assert status == 200
        base_revision = str(form_payload["revision"])

        status, preview = _request_json(
            "POST",
            f"{base_url}/api/workflow/form/preview",
            {
                "base_revision": base_revision,
                "node_creates": [{"node_id": "review", "handler": "review_handler"}],
                "node_edits": [],
                "edge_creates": [{"source": "review", "target": "finish"}],
                "edge_rewires": [{"edge_index": 2, "target": "review"}],
                "edge_edits": [],
                "ui_state": {
                    "positions": {
                        "router": {"x": 80, "y": 120},
                        "planner": {"x": 320, "y": 120},
                        "review": {"x": 560, "y": 120},
                        "finish": {"x": 800, "y": 120},
                    },
                    "edge_handles": {
                        "2": {"source_handle": "bottom-out", "target_handle": "top-in"},
                        "3": {"source_handle": "right-out", "target_handle": "left-in"},
                    },
                },
            },
        )
        assert status == 200
        assert preview["validation_report"]["is_valid"] is True
        node_ids = {node["id"] for node in preview["candidate_workflow"]["nodes"]}
        assert "review" in node_ids
        assert preview["candidate_workflow"]["edges"][2]["target"] == "review"
        assert preview["candidate_workflow"]["edges"][-1]["source"] == "review"
        assert preview["candidate_workflow"]["edges"][-1]["target"] == "finish"
        assert preview["candidate_ui_state"]["positions"]["review"]["x"] == 560
        assert preview["candidate_ui_state"]["edge_handles"]["2"]["source_handle"] == "bottom-out"

        status, save_payload = _request_json(
            "POST",
            f"{base_url}/api/workflow/save",
            {
                "workflow": preview["candidate_workflow"],
                "ui_state": preview["candidate_ui_state"],
                "base_revision": base_revision,
            },
        )
        assert status == 200
        assert save_payload["backup_id"]

        status, after_form = _request_json("GET", f"{base_url}/api/workflow/form")
        assert status == 200
        assert any(node["id"] == "review" for node in after_form["nodes"])
        assert any(
            edge["source"] == "review" and edge["target"] == "finish"
            for edge in after_form["edges"]
        )
        assert after_form["ui_state"]["positions"]["review"]["x"] == 560
        assert after_form["ui_state"]["edge_handles"]["2"]["source_handle"] == "bottom-out"
        assert after_form["ui_state"]["edge_handles"]["2"]["target_handle"] == "top-in"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_workflow_studio_api_save_accepts_node_rename_payload(tmp_path: Path) -> None:
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", _base_payload())
    backup_dir = tmp_path / ".yagra-backups"

    server = create_workflow_studio_server(
        workflow_path=workflow_path,
        backup_dir=backup_dir,
        host="127.0.0.1",
        port=0,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = _server_base_url(server)

    try:
        status, form_payload = _request_json("GET", f"{base_url}/api/workflow/form")
        assert status == 200
        base_revision = str(form_payload["revision"])

        candidate_workflow = deepcopy(form_payload["workflow"])
        for node in candidate_workflow["nodes"]:
            if node["id"] == "router":
                node["id"] = "entry"
        candidate_workflow["start_at"] = "entry"
        candidate_workflow["edges"] = [
            {
                **edge,
                "source": "entry" if edge["source"] == "router" else edge["source"],
                "target": "entry" if edge["target"] == "router" else edge["target"],
            }
            for edge in candidate_workflow["edges"]
        ]
        candidate_ui_state = {
            "positions": {
                "entry": {"x": 80, "y": 120},
                "planner": {"x": 320, "y": 120},
                "finish": {"x": 560, "y": 120},
            },
            "edge_handles": {
                "0": {"source_handle": "bottom-out", "target_handle": "top-in"},
            },
        }

        status, save_payload = _request_json(
            "POST",
            f"{base_url}/api/workflow/save",
            {
                "workflow": candidate_workflow,
                "ui_state": candidate_ui_state,
                "base_revision": base_revision,
            },
        )
        assert status == 200
        assert save_payload["backup_id"]

        status, after_form = _request_json("GET", f"{base_url}/api/workflow/form")
        assert status == 200
        assert after_form["workflow"]["start_at"] == "entry"
        node_ids = {node["id"] for node in after_form["workflow"]["nodes"]}
        assert "entry" in node_ids
        assert "router" not in node_ids
        assert all(
            edge["source"] != "router" and edge["target"] != "router"
            for edge in after_form["workflow"]["edges"]
        )
        assert "entry" in after_form["ui_state"]["positions"]
        assert "router" not in after_form["ui_state"]["positions"]
        assert after_form["ui_state"]["edge_handles"]["0"]["source_handle"] == "bottom-out"
        assert after_form["ui_state"]["edge_handles"]["0"]["target_handle"] == "top-in"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_workflow_studio_api_supports_single_node_without_edges(tmp_path: Path) -> None:
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", {})
    backup_dir = tmp_path / ".yagra-backups"

    server = create_workflow_studio_server(
        workflow_path=workflow_path,
        backup_dir=backup_dir,
        host="127.0.0.1",
        port=0,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = _server_base_url(server)

    try:
        status, form_payload = _request_json("GET", f"{base_url}/api/workflow/form")
        assert status == 200
        base_revision = str(form_payload["revision"])

        candidate_workflow = {
            "version": "1.0",
            "start_at": "solo",
            "end_at": ["solo"],
            "nodes": [{"id": "solo", "handler": "solo_handler"}],
            "edges": [],
            "params": {},
        }
        candidate_ui_state = {
            "positions": {"solo": {"x": 140, "y": 120}},
        }

        status, save_payload = _request_json(
            "POST",
            f"{base_url}/api/workflow/save",
            {
                "workflow": candidate_workflow,
                "ui_state": candidate_ui_state,
                "base_revision": base_revision,
            },
        )
        assert status == 200
        assert save_payload["backup_id"]

        status, after_form = _request_json("GET", f"{base_url}/api/workflow/form")
        assert status == 200
        assert after_form["workflow"]["start_at"] == "solo"
        assert after_form["workflow"]["end_at"] == ["solo"]
        assert len(after_form["workflow"]["nodes"]) == 1
        assert len(after_form["workflow"]["edges"]) == 0
        assert after_form["validation_report"]["is_valid"] is True
        assert after_form["ui_state"]["positions"]["solo"]["x"] == 140
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_workflow_studio_api_validate_live(tmp_path: Path) -> None:
    """Tests the POST /api/workflow/validate endpoint for live validation."""
    workspace_root = tmp_path / "workspace"
    _write_workflow(workspace_root / "workflows" / "test.yaml", _base_payload())

    server = create_workflow_studio_server(
        workflow_path=workspace_root / "workflows" / "test.yaml",
        workspace_root=workspace_root,
        backup_dir=tmp_path / ".yagra-backups",
        host="127.0.0.1",
        port=0,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = _server_base_url(server)

    try:
        # Valid workflow -> passes validation
        valid_workflow = _base_payload()
        status, payload = _request_json(
            "POST",
            f"{base_url}/api/workflow/validate",
            {"workflow": valid_workflow},
        )
        assert status == 200
        assert payload["validation_report"]["is_valid"] is True

        # Invalid workflow (start_at references non-existent node) -> fails validation
        invalid_workflow = deepcopy(valid_workflow)
        invalid_workflow["start_at"] = "nonexistent"
        status, payload = _request_json(
            "POST",
            f"{base_url}/api/workflow/validate",
            {"workflow": invalid_workflow},
        )
        assert status == 200
        assert payload["validation_report"]["is_valid"] is False
        assert len(payload["validation_report"]["issues"]) > 0

        # Issues have severity field
        first_issue = payload["validation_report"]["issues"][0]
        assert "severity" in first_issue
        assert first_issue["severity"] in ("error", "warning", "info")

        # Missing workflow key -> 400
        status, payload = _request_json(
            "POST",
            f"{base_url}/api/workflow/validate",
            {},
        )
        assert status == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_workflow_studio_api_validate_live_returns_warnings(tmp_path: Path) -> None:
    """Tests that validate_live returns warning/info severity issues."""
    workspace_root = tmp_path / "workspace"

    # Create prompt file with {query} variable
    prompts_dir = workspace_root / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = prompts_dir / "test_prompts.yaml"
    prompt_file.write_text(
        yaml.safe_dump(
            {
                "responder": {
                    "system": "You are helpful.",
                    "user": "Answer: {query}",
                }
            }
        ),
        encoding="utf-8",
    )

    # Workflow using prompt_ref without state_schema -> should produce info/warning
    workflow_with_prompt_ref = {
        "version": "1.0",
        "start_at": "responder",
        "end_at": ["responder"],
        "nodes": [
            {
                "id": "responder",
                "handler": "llm",
                "params": {
                    "prompt_ref": "../prompts/test_prompts.yaml#responder",
                    "model": {"provider": "openai", "name": "gpt-4o-mini"},
                },
            },
        ],
        "edges": [],
        "params": {},
    }
    _write_workflow(
        workspace_root / "workflows" / "prompt_test.yaml",
        workflow_with_prompt_ref,
    )

    server = create_workflow_studio_server(
        workflow_path=workspace_root / "workflows" / "prompt_test.yaml",
        workspace_root=workspace_root,
        backup_dir=tmp_path / ".yagra-backups",
        host="127.0.0.1",
        port=0,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = _server_base_url(server)

    try:
        status, payload = _request_json(
            "POST",
            f"{base_url}/api/workflow/validate",
            {"workflow": workflow_with_prompt_ref},
        )
        assert status == 200
        report = payload["validation_report"]
        # is_valid should be True because only warning/info issues
        assert report["is_valid"] is True
        # Should have at least one issue (info about missing state_schema)
        assert len(report["issues"]) > 0
        severities = {i["severity"] for i in report["issues"]}
        # All issues should be warning or info (not error)
        assert "error" not in severities
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
