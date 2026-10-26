from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi_server import FastAPIServer
from utilities.workflow import Workflow
from utilities.workflow_errors import WorkflowExecutionError
from worker.tasks import control_flows, tools


CHILD_FAILURE = {
    "node_id": "child-node", "task_name": "tools.programming_function",
    "code": "NODE_EXECUTION_FAILED", "exception_type": "ValueError", "message": "Child input is invalid",
}


@pytest.mark.parametrize("module,task_name,async_data", [
    (tools, "workflow_invoke", {"record_ids": ["child-run"], "finished_record_ids": [], "output_fields_batches": {}}),
    (control_flows, "workflow_selector", {"record_id": "child-run"}),
    (control_flows, "workflow_loop", {"record_id": "child-run", "output_fields": {},
                                      "output_fields_cumulative": {}, "loop_count": 1, "used_credits": 0}),
])
def test_nested_failure_preserves_child_details_without_retry(monkeypatch, module, task_name, async_data):
    record = SimpleNamespace(data={"failures": [CHILD_FAILURE]}, rid="child-run", status="FAILED")
    query = SimpleNamespace(join=lambda *args: query, where=lambda *args: query, first=lambda: record)
    monkeypatch.setattr(module.WorkflowRunRecord, "select", lambda *args: query)
    monkeypatch.setattr(Workflow, "get_async_task", lambda *args: async_data)
    monkeypatch.setattr(Workflow, "report_workflow_status", lambda *args: True)
    node_task = getattr(module, task_name)
    monkeypatch.setattr(node_task, "retry", lambda *args, **kwargs: pytest.fail("Failed child was retried"))
    monkeypatch.setattr(module, "run_workflow_common", lambda **kwargs: pytest.fail("Failed child was rerun"))
    fields = {"judgement_model": {"value": "openai\u22c4unused"}, "max_loop_count": {"value": 2}}
    data = {"nodes": [{"id": "parent-node", "type": "Test", "category": "tools", "data": {
        "task_name": f"{module.__name__.split('.')[-1]}.{task_name}", "template": fields,
    }}], "edges": []}

    with pytest.raises(WorkflowExecutionError, match="Child input is invalid") as error:
        node_task(data, "parent-node")

    assert error.value.failures == [CHILD_FAILURE]
    assert CHILD_FAILURE in data["failures"]
    assert data["nodes"][0]["data"]["status"] == 500


class MemoryCache(dict):
    def set(self, key, value, expire=None):
        self[key] = value


@pytest.fixture
def api_client(monkeypatch):
    import utilities.config

    monkeypatch.setattr(utilities.config, "cache", MemoryCache())
    server = FastAPIServer.__new__(FastAPIServer)
    server.fastapi_app = FastAPI()
    server.workflow_api = SimpleNamespace(
        get=lambda payload: {"status": 200, "data": {"data": {"nodes": [], "edges": []}}},
        run=lambda payload: {"status": 200, "data": {"rid": "failed-run"}},
    )
    server.workflow_run_record_api = SimpleNamespace(get=lambda payload: {"status": 200, "data": {
        "rid": "failed-run", "status": "FAILED", "data": {"failures": [CHILD_FAILURE], "error_task": "legacy-task"},
    }})
    server.setup_workflow_endpoints()
    return TestClient(server.fastapi_app)


def test_fastapi_stop_delegates_and_waiting_states_are_truthful(monkeypatch):
    import utilities.config

    monkeypatch.setattr(utilities.config, "cache", MemoryCache())
    server = FastAPIServer.__new__(FastAPIServer)
    server.fastapi_app = FastAPI()
    server.workflow_api = SimpleNamespace(
        get=lambda payload: {"status": 200, "data": {"data": {"nodes": [], "edges": []}}},
        run=lambda payload: {"status": 200, "data": {"rid": "stopped-run"}},
    )
    calls = []
    server.workflow_run_record_api = SimpleNamespace(
        get=lambda payload: {"status": 200, "data": {"status": "STOPPED", "data": {"nodes": [], "edges": []}}},
        stop=lambda payload: (calls.append(payload) or {"status": 200, "msg": "STOPPED", "data": {"status": "STOPPED"}}),
    )
    server.setup_workflow_endpoints()
    client = TestClient(server.fastapi_app)
    stopped = client.post("/api/workflow/workflow-id/stop/stopped-run").json()
    assert stopped["status"] == 200 and stopped["msg"] == "STOPPED"
    assert calls == [{"wid": "workflow-id", "rid": "stopped-run"}]
    checked = client.post("/api/workflow/check-status", json={"rid": "stopped-run"}).json()
    assert checked["status"] == 200 and checked["msg"] == "STOPPED"
    waited = client.post("/api/workflow/run", json={"wid": "workflow-id", "wait_for_completion": True}).json()
    assert waited["status"] == 200 and waited["msg"] == "STOPPED"
    server.workflow_run_record_api.get = lambda payload: {"status": 200, "data": {"status": "STOPPING", "data": {}}}
    checked = client.post("/api/workflow/check-status", json={"rid": "stopped-run"}).json()
    assert checked["status"] == 202 and checked["msg"] == "STOPPING"
    server.workflow_run_record_api.get = lambda payload: {"status": 200, "data": {
        "status": "PAUSED", "data": {"pending_feedback_nodes": ["review"]}}}
    checked = client.post("/api/workflow/check-status", json={"rid": "stopped-run"}).json()
    assert checked["status"] == 102 and checked["msg"] == "PAUSED"
    waited = client.post("/api/workflow/run", json={"wid": "workflow-id", "wait_for_completion": True}).json()
    assert waited["status"] == 102 and waited["data"]["pending_feedback_nodes"] == ["review"]


@pytest.mark.parametrize("path,payload", [
    ("/api/workflow/check-status", {"rid": "failed-run"}),
    ("/api/workflow/run", {"wid": "workflow", "wait_for_completion": True}),
])
def test_fastapi_failed_runs_return_structured_failure_instead_of_outputs(api_client, path, payload):
    response = api_client.post(path, json=payload).json()

    assert response["status"] == 500
    assert response["msg"] == "FAILED"
    assert response["data"] == {
        "error": "WORKFLOW_FAILED", "rid": "failed-run", "status": "FAILED", "failures": [CHILD_FAILURE],
        "next_action": "inspect_error", "replay_safety": "unknown",
    }
