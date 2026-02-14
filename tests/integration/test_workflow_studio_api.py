from __future__ import annotations

import json
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
    """テストサーバーの base URL を組み立てる。

    Args:
        server: `ThreadingHTTPServer` 互換オブジェクト。

    Returns:
        base URL 文字列。
    """
    address = server.server_address
    raw_host = address[0]
    host = raw_host.decode("utf-8") if isinstance(raw_host, bytes) else str(raw_host)
    port = int(address[1])
    return f"http://{host}:{port}"


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
        candidate_ui_state = {"positions": {"router": {"x": 150, "y": 200}}}

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

        status, rollback_response = _request_json(
            "POST",
            f"{base_url}/api/workflow/rollback",
            {"backup_id": save_response["backup_id"]},
        )
        assert status == 200
        assert rollback_response["restored_revision"] == base_revision

        status, after = _request_json("GET", f"{base_url}/api/workflow")
        assert status == 200
        assert after["revision"] == base_revision
        assert after["workflow"]["params"] == {}
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


def test_workflow_studio_form_preview_and_save(tmp_path: Path) -> None:
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
        assert len(form_payload["nodes"]) == 3
        assert len(form_payload["edges"]) == 3

        status, preview = _request_json(
            "POST",
            f"{base_url}/api/workflow/form/preview",
            {
                "base_revision": base_revision,
                "node_edits": [
                    {
                        "node_id": "planner",
                        "prompt": {"system": "edited prompt"},
                        "model": {"provider": "openai", "name": "gpt-4.1-nano"},
                    }
                ],
                "edge_edits": [{"edge_index": 2, "condition": "done"}],
            },
        )
        assert status == 200
        assert preview["summary"]["total"] >= 1
        assert preview["validation_report"]["is_valid"] is True
        assert (
            preview["candidate_workflow"]["nodes"][1]["params"]["prompt"]["system"]
            == "edited prompt"
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
        assert planner["prompt"]["system"] == "edited prompt"
        assert planner["model"]["name"] == "gpt-4.1-nano"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
