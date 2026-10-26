from __future__ import annotations

import json
import threading
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest


@pytest.fixture
def local_http(monkeypatch):
    from utilities import http_request

    received = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            received.append((self.command, self.path, body))
            path = urlsplit(self.path).path
            if path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/success")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            status = 422 if path == "/error" else 201
            output = {"received": json.loads(body) if body else None,
                      "query": parse_qs(urlsplit(self.path).query), "method": self.command}
            if status == 422:
                output["detail"] = "synthetic-response-secret"
            encoded = json.dumps(output).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("X-Test-Response", "preserved")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        do_POST = do_GET

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(http_request, "new_httpx_client", lambda **kwargs: httpx.Client(trust_env=False))
    try:
        yield f"http://127.0.0.1:{server.server_port}", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def node(identity, kind, task_name, values, outputs):
    fields = {name: {"value": value, "type": "any"} for name, value in values.items()}
    fields.update({name: {"value": "", "is_output": True} for name in outputs})
    return {"id": identity, "type": kind, "category": "tools",
            "data": {"task_name": task_name, "template": fields}}


def execute(definition):
    from background_task.workflow_tasks import run_workflow
    from celery_worker import app
    from models import Workflow as WorkflowModel, WorkflowRunRecord, create_tables, database

    create_tables()
    model = WorkflowModel.create(title="HTTP integration", data=deepcopy(definition))
    record = WorkflowRunRecord.create(workflow=model, data=deepcopy(definition), status="RUNNING", run_from="CLI")
    data = deepcopy(definition)
    data.update(wid=model.wid.hex, rid=record.rid.hex)
    original_eager = app.conf.task_always_eager
    original_propagates = app.conf.task_eager_propagates
    app.conf.update(task_always_eager=True, task_eager_propagates=False)
    try:
        try:
            run_workflow.run(data).get(propagate=True)
        except Exception:
            pass
    finally:
        app.conf.update(task_always_eager=original_eager, task_eager_propagates=original_propagates)
    database.close()
    return WorkflowRunRecord.get_by_id(record.rid)


def test_actual_workflow_routes_typed_http_outputs_to_downstream(local_http):
    from utilities.workflow import Workflow

    base, received = local_http
    definition = {"nodes": [
        node("source", "ProgrammingFunction", "tools.programming_function", {
            "language": "python", "code": "def main(): return {'zero': 0, 'enabled': False, 'items': [1, 2]}"}, ("output",)),
        node("request", "HttpRequest", "tools.http_request", {
            "url": base + "/success?existing=1", "method": "POST", "body_type": "json", "body": {},
            "query_params": {"added": "yes"}}, ("status_code", "response_headers", "response_body", "response_json")),
        node("downstream", "ProgrammingFunction", "tools.programming_function", {
            "language": "python", "payload": {}, "status": 0, "headers": {},
            "code": "def main(payload, status, headers):\n    assert status == 201\n    assert headers['x-test-response'] == 'preserved'\n    assert payload['received']['enabled'] is False\n    assert payload['received']['items'] == [1, 2]\n    return payload['received']['zero']"}, ("output",)),
    ], "edges": [
        {"source": "source", "sourceHandle": "output", "target": "request", "targetHandle": "body"},
        *[{"source": "request", "sourceHandle": output, "target": "downstream", "targetHandle": target}
          for output, target in (("response_json", "payload"), ("status_code", "status"), ("response_headers", "headers"))],
    ]}
    saved = execute(definition)
    assert saved.status == "FINISHED", saved.data.get("failures")
    workflow = Workflow(saved.data)
    assert workflow.get_node_field_value("downstream", "output") == 0
    assert len(received) == 1
    assert received[0][0] == "POST"
    assert parse_qs(urlsplit(received[0][1]).query) == {"existing": ["1"], "added": ["yes"]}
    assert workflow.get_node("request").status == 200


def test_http_error_persists_outputs_stops_side_effect_and_can_be_handled(local_http, tmp_path):
    from utilities.workflow import Workflow
    from utilities.workflow_errors import workflow_error_payload

    base, received = local_http
    marker = tmp_path / "downstream-side-effect.txt"
    definition = {"nodes": [
        node("request", "HttpRequest", "tools.http_request", {
            "url": base + "/error?token=synthetic-query-secret", "headers": {"Authorization": "Bearer synthetic-header-secret"},
            "fail_on_http_error": True}, ("status_code", "response_headers", "response_body", "response_json")),
        node("downstream", "ProgrammingFunction", "tools.programming_function", {
            "language": "python", "status": 0,
            "code": f"from pathlib import Path\ndef main(status):\n    Path({str(marker)!r}).write_text('executed')\n    return status"}, ("output",)),
    ], "edges": [{"source": "request", "sourceHandle": "status_code", "target": "downstream", "targetHandle": "status"}]}
    saved = execute(definition)
    assert saved.status == "FAILED"
    workflow = Workflow(saved.data)
    assert workflow.get_node("request").status == 500
    assert workflow.get_node_field_value("request", "status_code") == 422
    assert workflow.get_node_field_value("request", "response_json")["detail"] == "synthetic-response-secret"
    assert not marker.exists()
    diagnostics = workflow_error_payload(saved)
    assert diagnostics["failures"][0]["node_id"] == "request"
    assert "422" in diagnostics["failures"][0]["message"]
    for secret in ("synthetic-query-secret", "synthetic-header-secret", "synthetic-response-secret"):
        assert secret not in json.dumps(diagnostics)

    definition["nodes"][0]["data"]["template"]["fail_on_http_error"]["value"] = False
    definition["nodes"][1]["data"]["template"]["code"]["value"] = "def main(status): return status"
    handled = execute(definition)
    assert handled.status == "FINISHED"
    assert Workflow(handled.data).get_node_field_value("downstream", "output") == 422
    assert len(received) == 2
    assert not marker.exists()


def test_redirects_require_explicit_opt_in(local_http):
    from utilities.http_request import perform_http_request

    base, received = local_http
    assert perform_http_request(url=base + "/redirect")["status_code"] == 302
    assert [urlsplit(item[1]).path for item in received] == ["/redirect"]
    assert perform_http_request(url=base + "/redirect", follow_redirects=True)["status_code"] == 201
    assert [urlsplit(item[1]).path for item in received] == ["/redirect", "/redirect", "/success"]
