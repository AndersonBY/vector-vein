from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


CLI = Path(__file__).resolve().parents[1] / "cli.py"


@pytest.mark.parametrize("stored", [{"message": "malformed"}, "malformed", None, [None, "bad", 42]])
def test_malformed_legacy_failure_records_still_have_safe_fallback(stored, monkeypatch):
    from utilities.workflow_errors import workflow_error_payload
    monkeypatch.setattr("utilities.config.Settings", lambda: SimpleNamespace(data={}))
    record = {"rid": "old-run", "status": "FAILED", "data": {"failures": stored, "error_task": "tools.example"}}
    payload = workflow_error_payload(record)
    assert payload["status"] == "FAILED"
    assert payload["failures"][0]["task_name"] == "tools.example"
    assert payload["next_action"] == "inspect_error"


def test_nested_configuration_and_secret_objects_are_redacted(monkeypatch):
    from pydantic import BaseModel, SecretStr
    from utilities.workflow_errors import node_failure, workflow_error_payload

    class Credentials(BaseModel):
        private_key: SecretStr

    monkeypatch.setattr("utilities.config.Settings", lambda: SimpleNamespace(data={
        "credentials": {"nested": {"private_key": "nested-config-secret"}},
        "model": Credentials(private_key=SecretStr("pydantic-secret")),
        "unused_credential": SecretStr(""),
    }))
    data = {"related_workflows": {"child": {"credentials": {"nested": {"value": "child-secret"}}}}}
    failure = node_failure(ValueError("nested-config-secret pydantic-secret child-secret"), data, "node", "tools.example")
    assert failure["message"] == "[REDACTED] [REDACTED] [REDACTED]"
    data["failures"] = [None, "broken", failure]
    assert workflow_error_payload({"rid": "run", "status": "FAILED", "data": data})["failures"] == [failure]


def test_failed_chat_projection_cannot_rollback_sqlite_run_records(tmp_path):
    script = r'''
import json
import sys
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, sys.argv[1])
from models import Workflow as WorkflowModel, WorkflowRunRecord, create_tables, database
from utilities.config import cache, config
from utilities.workflow import Workflow
from utilities.workflow_errors import add_failure, node_failure

create_tables()
workflow = WorkflowModel.create(title="chat projection persistence", data={"nodes": [], "edges": []})
results = []
try:
    for operation in ("lookup", "save"):
        data = {"nodes": [], "edges": []}
        record = WorkflowRunRecord.create(workflow=workflow, data=data, status="RUNNING", run_from="CHAT")
        data["rid"] = record.rid.hex
        add_failure(data, node_failure(ValueError("original failure"), data, "failed-node", "tools.example"))

        def broken(*args, **kwargs):
            raise RuntimeError("chat projection unavailable")

        message = SimpleNamespace(status="R", metadata={}, save=broken)
        replacement = SimpleNamespace(get=broken if operation == "lookup" else lambda **kwargs: message,
                                      StatusTypes=SimpleNamespace(RUNNING_WORKFLOW="R", WORKFLOW_FAILED="Z", SUCCESS="S"))
        with patch("utilities.workflow.workflow.Message", replacement):
            assert Workflow(deepcopy(data)).report_workflow_status(500, "tools.example")
        database.close()
        saved = WorkflowRunRecord.get_by_id(record.rid)
        assert saved.status == "FAILED"
        assert saved.data["failures"][0]["message"] == "original failure"
        if operation == "save":
            assert message.status == "Z"
            assert json.loads(message.metadata["workflow_result"])["status"] == "FAILED"
        results.append(operation)
    print(json.dumps(results))
finally:
    cache.close()
    database.close()
    config.close()
'''
    environment = {key: value for key, value in os.environ.items()
                   if key not in ("VECTORVEIN_LLM_SETTINGS_FILE", "VECTORVEIN_OUTPUT_DIR")}
    process = subprocess.run([sys.executable, "-X", "utf8", "-c", script, str(CLI.parent)],
                             cwd=tmp_path, env=environment, capture_output=True, text=True,
                             encoding="utf-8", timeout=120)
    assert process.returncode == 0, process.stderr + process.stdout
    assert '["lookup", "save"]' in process.stdout


def programming_node(identity, code, **inputs):
    fields = {name: {"value": value, "type": "str"} for name, value in inputs.items()}
    fields.update(language={"value": "python"}, code={"value": code})
    for name in ("output", "error_msg", "console_msg", "files"):
        fields[name] = {"value": "", "is_output": True}
    return {"id": identity, "type": "ProgrammingFunction", "category": "tools",
            "data": {"task_name": "tools.programming_function", "template": fields}}


def test_cli_parallel_failures_survive_new_process_and_stop_downstream(tmp_path):
    workspace = tmp_path / "runtime"
    marker = tmp_path / "downstream-must-not-run.txt"
    secret = "synthetic-integration-secret"
    nodes = [
        programming_node("fail-a", "def main(api_key): raise ValueError('人工验收：输入格式不正确 ' + api_key)", api_key=secret),
        programming_node("fail-b", "def main(): raise LookupError('missing source row')"),
        programming_node("sibling", "def main(): return 'sibling completed'"),
        programming_node("downstream", f"from pathlib import Path\ndef main(value):\n    Path({str(marker)!r}).write_text('unexpected')\n    return value", value=""),
    ]
    definition = {"nodes": nodes, "edges": [{"id": "edge", "source": "fail-a", "sourceHandle": "output",
                                            "target": "downstream", "targetHandle": "value"}]}
    workflow_file = tmp_path / "workflow.json"
    workflow_file.write_text(json.dumps(definition, ensure_ascii=False), encoding="utf-8")
    environment = {key: value for key, value in os.environ.items()
                   if key not in ("VECTORVEIN_LLM_SETTINGS_FILE", "VECTORVEIN_OUTPUT_DIR")}

    def command(*arguments, expected=0):
        process = subprocess.run([sys.executable, "-X", "utf8", str(CLI), "--workspace", str(workspace),
                                  "--output-dir", str(tmp_path / "output"), *map(str, arguments)],
                                 cwd=tmp_path, env=environment, capture_output=True, text=True,
                                 encoding="utf-8", timeout=120)
        assert process.returncode == expected, process.stderr + process.stdout
        assert secret not in process.stderr
        return json.loads(process.stdout)

    created = command("workflow", "create", "--file", workflow_file)
    failed = command("workflow", "run", created["wid"], expected=1)
    assert failed["status"] == "FAILED" and failed["error"] == "WORKFLOW_FAILED"
    assert failed["replay_safety"] == "unknown" and failed["next_action"] == "inspect_error"
    assert secret not in json.dumps(failed)
    failures = {item["node_id"]: item for item in failed["failures"]}
    assert set(failures) == {"fail-a", "fail-b"}
    assert failures["fail-a"]["exception_type"] == "ValueError"
    assert "人工验收：输入格式不正确" in failures["fail-a"]["message"]
    assert "[REDACTED]" in failures["fail-a"]["message"]
    assert failures["fail-b"]["exception_type"] == "LookupError"
    assert "missing source row" in failures["fail-b"]["message"]
    assert failed["outputs"]["sibling"]["output"] == "sibling completed"
    assert not marker.exists()

    persisted = command("workflow", "status", failed["rid"], "--full")
    assert persisted["status"] == "FAILED" and persisted["failures"] == failed["failures"]
    assert persisted["data"]["error_task"]
    assert "_batch_collecting" not in persisted["data"]
    snapshots = {node["id"]: node for node in persisted["data"]["nodes"]}
    assert snapshots["fail-a"]["data"]["status"] == 500
    assert snapshots["fail-b"]["data"]["status"] == 500
    assert snapshots["sibling"]["data"]["status"] == 200
    assert not marker.exists()

    override = tmp_path / "success.json"
    override.write_text(json.dumps([
        {"node_id": "fail-a", "field_name": "code", "value": "def main(api_key): return 'fixed'"},
        {"node_id": "fail-b", "field_name": "code", "value": "def main(): return 'also fixed'"},
        {"node_id": "downstream", "field_name": "code", "value": "def main(value): return value.upper()"},
    ]), encoding="utf-8")
    successful = command("workflow", "run", created["wid"], "--inputs", override)
    assert successful["status"] == "FINISHED"
    assert successful["outputs"]["downstream"]["output"] == "FIXED"
    assert successful["outputs"]["sibling"]["output"] == "sibling completed"
    assert not successful.get("failures")
