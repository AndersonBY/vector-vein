from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from utilities.workflow import Workflow
from utilities.workflow import workflow as workflow_module
from utilities import workflow_messages
from utilities.workflow_errors import (
    WorkflowExecutionError, WorkflowInputError, add_failure, node_failure, workflow_error_payload,
)
from worker.tasks import task
from background_task import workflow_tasks


def workflow_data(*node_ids):
    return {"rid": "run-1", "wid": "workflow-1", "edges": [], "nodes": [
        {"id": node_id, "type": "Test", "category": "tools", "data": {
            "task_name": "tools.example", "template": {"output": {"value": ""}}}}
        for node_id in node_ids
    ]}


@pytest.fixture(autouse=True)
def no_settings_database(monkeypatch):
    monkeypatch.setattr("utilities.config.Settings", lambda: SimpleNamespace(data={"api_key": "settings-secret"}))


def test_failure_messages_are_bounded_redacted_and_input_codes_are_explicit():
    data = workflow_data("node")
    data["nodes"][0]["data"]["template"]["api_key"] = {"value": "node-secret"}
    data["related_workflows"] = {"child": {"password": "child-secret"}}
    message = "node-secret settings-secret child-secret https://name:pass@example.com Bearer auth-secret token=query-secret " + "x" * 2000
    failure = node_failure(ValueError(message), data, "node", "tasks.tools.example")
    assert failure["code"] == "NODE_EXECUTION_FAILED"
    assert failure["task_name"] == "tools.example"
    assert len(failure["message"]) == 1500
    for secret in ("node-secret", "settings-secret", "child-secret", "name:pass", "auth-secret", "query-secret"):
        assert secret not in failure["message"]
    assert node_failure(WorkflowInputError("bad input"), data)["code"] == "INVALID_ARGUMENT"
    for index in range(12):
        add_failure(data, {**failure, "node_id": str(index)})
    assert len(data["failures"]) == 8


def test_sensitive_node_field_metadata_is_not_treated_as_secret():
    data = workflow_data("node")
    data["nodes"][0]["data"]["template"]["api_key"] = {"value": "node-secret", "type": "str", "field_type": "input"}
    assert node_failure(RuntimeError("str input node-secret"), data)["message"] == "str input [REDACTED]"


def test_single_node_failure_keeps_real_reason_status_and_runtime(monkeypatch):
    saved = []
    monkeypatch.setattr(Workflow, "report_workflow_status", lambda self, *args: saved.append(deepcopy(self.data)))

    @task
    def single_fail(data, node_id):
        raise RuntimeError("Connection refused")

    with pytest.raises(RuntimeError, match="Connection refused"):
        single_fail(workflow_data("node"), "node")
    assert len(saved) == 1
    assert saved[0]["failures"][0]["message"] == "Connection refused"
    assert saved[0]["failures"][0]["node_id"] == "node"
    assert saved[0]["nodes"][0]["data"]["status"] == 500
    assert saved[0]["node_run_time"]["node"] >= 0


def test_unknown_task_dispatch_identifies_node_without_replaying_workflow(monkeypatch):
    saved = []
    monkeypatch.setattr(Workflow, "report_workflow_status", lambda self, *args: saved.append(deepcopy(self.data)))
    monkeypatch.setattr(workflow_tasks, "task_functions", {})
    data = workflow_data("node")
    with pytest.raises(KeyError):
        workflow_tasks.run_workflow.run(data)
    assert len(saved) == 1
    assert saved[0]["failures"][0]["node_id"] == "node"
    assert saved[0]["failures"][0]["task_name"] == "tools.example"
    assert saved[0]["failures"][0]["exception_type"] == "KeyError"
    assert saved[0]["nodes"][0]["data"]["status"] == 500


def test_batch_collects_every_failure_and_preserves_successes_and_skips(monkeypatch):
    persisted = []
    reported = []
    completed = []
    monkeypatch.setattr(Workflow, "report_workflow_status", lambda self, *args: persisted.append(deepcopy(self.data)))
    monkeypatch.setattr(Workflow, "report_node_status", lambda self, node_id: reported.append(node_id))

    @task
    def batch_fail(data, node_id):
        completed.append(node_id)
        raise RuntimeError(f"failure at {node_id}")

    @task
    def success(data, node_id):
        wf = Workflow(data)
        wf.update_node_field_value(node_id, "output", "completed result")
        wf.set_node_status(node_id, 200)
        completed.append(node_id)
        return wf.data

    monkeypatch.setattr(workflow_tasks, "task_functions", {"test": {"fail": batch_fail, "success": success}})
    data = workflow_data("first", "second", "success", "skipped")
    data["skipped_nodes"] = ["skipped"]
    tasks = [{"node_id": node_id, "task_name": f"test.{function}"} for node_id, function in (
        ("first", "fail"), ("second", "fail"), ("success", "success"), ("skipped", "success"))]
    with pytest.raises(WorkflowExecutionError):
        workflow_tasks.batch_tasks.run(data, tasks)
    assert set(completed) == {"first", "second", "success"}
    assert reported == ["first", "second", "success", "skipped"]
    assert len(persisted) == 1
    result = persisted[0]
    assert {failure["node_id"] for failure in result["failures"]} == {"first", "second"}
    assert "_batch_collecting" not in result
    nodes = {node["id"]: node for node in result["nodes"]}
    assert nodes["success"]["data"]["template"]["output"]["value"] == "completed result"
    assert nodes["success"]["data"]["status"] == 200
    assert nodes["first"]["data"]["status"] == nodes["second"]["data"]["status"] == 500
    assert set(result["node_run_time"]) == {"first", "second", "success"}
    assert "run_time" not in nodes["skipped"]


def install_record(monkeypatch, data, run_from="CHAT"):
    from contextlib import nullcontext
    events = []
    record = SimpleNamespace(rid="run-1", data=data, status="RUNNING", run_from=run_from,
                             source_message="message-1", save=lambda: events.append("record"))
    monkeypatch.setattr(workflow_module, "WorkflowRunRecord", SimpleNamespace(
        rid="rid", status="RUNNING", get=lambda *args: record,
        update=lambda **kwargs: SimpleNamespace(where=lambda *args: SimpleNamespace(execute=lambda: (events.append("record") or 1))),
        RunFromTypes=SimpleNamespace(CHAT="CHAT")))
    monkeypatch.setattr(workflow_module, "cache", SimpleNamespace(transact=nullcontext, set=lambda *args: events.append("cache")))
    return record, events


def test_failed_chat_metadata_is_json_error_and_record_is_saved_first(monkeypatch):
    data = workflow_data("node")
    add_failure(data, node_failure(RuntimeError("offline"), data, "node", "tools.example"))
    record, events = install_record(monkeypatch, data)
    record.rid = SimpleNamespace(hex="run-1")
    message = SimpleNamespace(mid="message-1", status="R", metadata={"record_id": "run-1"})
    def update(**kwargs):
        def execute():
            events.append("message")
            message.status, message.metadata = kwargs["status"], kwargs["metadata"]
            return 1
        return SimpleNamespace(where=lambda *args: SimpleNamespace(execute=execute))
    monkeypatch.setattr(workflow_messages, "Message", SimpleNamespace(
        mid="mid", metadata="metadata", get_or_none=lambda *args: message, update=update,
        StatusTypes=SimpleNamespace(RUNNING_WORKFLOW="R", WORKFLOW_FAILED="Z", SUCCESS="S")))
    assert Workflow(data).report_workflow_status(500, "tools.example")
    assert events == ["record", "cache", "message"]
    assert record.status == "FAILED" and message.status == "Z"
    assert message.metadata["recordStatus"] == "FAILED"
    payload = json.loads(message.metadata["workflow_result"])
    assert payload["failures"][0]["message"] == "offline"
    assert payload["next_action"] == "inspect_error" and payload["replay_safety"] == "unknown"


def test_message_projection_failure_does_not_lose_persisted_failure(monkeypatch):
    data = workflow_data("node")
    record, events = install_record(monkeypatch, data)
    monkeypatch.setattr(workflow_messages.Message, "get_or_none", lambda *args: (_ for _ in ()).throw(RuntimeError()))
    assert Workflow(data).report_workflow_status(500, "tools.example")
    assert record.status == "FAILED" and events == ["record", "cache"]


def test_outer_dispatch_error_does_not_overwrite_persisted_node_evidence(monkeypatch):
    data = workflow_data("node")
    add_failure(data, node_failure(RuntimeError("original reason"), data, "node", "tools.example"))
    record, _ = install_record(monkeypatch, data, run_from="WEB")
    record.status = "FAILED"
    record.data["error_task"] = "tools.example"
    assert Workflow(workflow_data("node")).report_workflow_status(500, "workflow.run")
    assert record.data["failures"][0]["message"] == "original reason"
    assert record.data["error_task"] == "tools.example"


def test_legacy_and_cli_failure_payloads_keep_replay_safety_unknown():
    from cli import record_result
    import uuid
    record = SimpleNamespace(rid=uuid.uuid4(), workflow=SimpleNamespace(wid=uuid.uuid4()),
                             workflow_version=1, status="FAILED", data={"nodes": [], "error_task": "tools.example"})
    result = record_result(record)
    assert result["failures"][0]["task_name"] == "tools.example"
    assert result["replay_safety"] == "unknown"
    assert workflow_error_payload({"rid": result["rid"], "status": "FAILED", "data": record.data})["failures"] == result["failures"]


def test_execution_error_survives_celery_json_exception_roundtrip():
    from celery_worker import app
    failure = node_failure(RuntimeError("offline"), {}, "node", "tools.example")
    encoded = app.backend.prepare_exception(WorkflowExecutionError([failure]), serializer="json")
    restored = app.backend.exception_to_python(json.loads(json.dumps(encoded)))
    assert isinstance(restored, WorkflowExecutionError)
    assert restored.failures == [failure]
    assert str(restored) == "offline"


def test_llm_batch_retains_concrete_parallel_causes_without_exposing_credentials():
    from worker.tasks.llms.base_llm import BaseLLMTask
    llm = BaseLLMTask.__new__(BaseLLMTask)
    data = workflow_data("node")
    data["nodes"][0]["data"]["task_name"] = "llms.local_llm"
    llm.workflow = Workflow(data)
    llm.node_id = "node"
    llm.prompts = llm.input_prompt = ["first", "second"]
    llm.content_outputs = ["", ""]
    llm.reasoning_content_outputs = ["", ""]
    llm.function_call_outputs = [[], []]
    llm.function_call_arguments_batches = [{}, {}]
    llm.total_prompt_tokens = llm.total_completion_tokens = 0
    llm.use_function_call = False
    llm.get_max_concurrent_requests = lambda: 2

    def fail(prompt, index):
        if index == 0:
            raise ValueError("Invalid API key api_key=provider-secret settings-secret")
        raise TimeoutError("Provider connection timed out; Bearer auth-secret")

    llm.process_validated_prompt = fail
    with pytest.raises(RuntimeError, match="indexes: 0, 1"):
        llm.run()
    failures = llm.workflow.data["failures"]
    assert {failure["exception_type"] for failure in failures} == {"ValueError", "TimeoutError"}
    assert all(failure["code"] == "NODE_EXECUTION_FAILED" for failure in failures)
    assert any("Invalid API key" in failure["message"] for failure in failures)
    assert any("timed out" in failure["message"] for failure in failures)
    for failure in failures:
        assert "provider-secret" not in failure["message"]
        assert "settings-secret" not in failure["message"]
        assert "auth-secret" not in failure["message"]
    assert llm.workflow.get_node_field_value("node", "run_stats")["failures"] == [
        {"index": 0, "error": "ValueError"}, {"index": 1, "error": "TimeoutError"}]


@pytest.mark.parametrize("provider_error", [ValueError("Invalid API key: api_key=provider-secret"),
                                            TimeoutError("Provider connection timed out settings-secret")])
def test_real_llm_endpoint_loop_preserves_last_concrete_failure(monkeypatch, provider_error):
    from worker.tasks.llms import base_llm
    from vv_llm.types import BackendType
    llm = base_llm.BaseLLMTask.__new__(base_llm.BaseLLMTask)
    llm.workflow = Workflow(workflow_data("node"))
    llm.node_id = "node"
    llm.prompts = llm.input_prompt = ["test prompt"]
    llm.prompts_count = 1
    llm.content_outputs = [""]
    llm.reasoning_content_outputs = [""]
    llm.function_call_outputs = [[]]
    llm.function_call_arguments_batches = [{}]
    llm.total_prompt_tokens = llm.total_completion_tokens = 0
    llm.use_function_call = llm.stream = False
    llm.system_prompt = ""
    llm.model = "test-model"
    llm.MODEL_TYPE = BackendType.Local
    llm.temperature = llm.thinking = None
    llm.model_settings = SimpleNamespace(max_output_tokens=32, endpoints=["endpoint"])
    llm.SINGLE_PROCESS_TIMEOUT = 1
    llm.endpoint_available = lambda endpoint: True
    llm.get_max_concurrent_requests = lambda: 1
    llm.process_validated_prompt = llm.process_prompt
    calls = []

    def fail(*args):
        calls.append("provider")
        raise provider_error

    llm._create_completion_response = fail
    monkeypatch.setattr(base_llm, "create_chat_client", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(base_llm, "vv_llm_settings", SimpleNamespace(
        get_endpoint=lambda key: SimpleNamespace(id="endpoint", endpoint_type=None)))
    ticks = iter([0, 0, 2])
    monkeypatch.setattr(base_llm, "time", SimpleNamespace(time=lambda: next(ticks), sleep=lambda seconds: None))
    with pytest.raises(RuntimeError, match="indexes"):
        llm.run()
    assert calls == ["provider"]
    failure = llm.workflow.data["failures"][0]
    assert failure["exception_type"] == type(provider_error).__name__
    assert str(provider_error).split(" api_key")[0].split(" settings-secret")[0] in failure["message"]
    assert "provider-secret" not in failure["message"] and "settings-secret" not in failure["message"]
