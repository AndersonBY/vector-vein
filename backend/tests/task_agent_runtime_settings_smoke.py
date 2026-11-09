"""Actual App Server acceptance for model/policy changes and context compaction using a local fixture."""
from __future__ import annotations

from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import sys
import time

workspace = Path(sys.argv[1]).resolve()
port = int(sys.argv[2])
os.environ.pop("VECTORVEIN_LLM_SETTINGS_FILE", None)
os.environ.pop("VECTORVEIN_OUTPUT_DIR", None)
os.chdir(workspace)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cli import initialize  # noqa: E402
from models import Setting, database  # noqa: E402
from task_agent.service import TaskAgentService  # noqa: E402

with redirect_stdout(sys.stderr):
    initialize()
setting = Setting.select().order_by(Setting.create_time.desc()).first()
setting.data["llm_settings"] = {
    "VERSION": "2", "endpoints": [{"id": name, "api_base": f"http://127.0.0.1:{port}/{name}/v1", "api_key": "synthetic-runtime-test-key"} for name in ("one", "two")],
    "backends": {"local": {"models": {name: {"id": "same-wire-model", "enabled": True, "endpoints": [endpoint],
        "function_call_available": True, "context_length": window, "max_output_tokens": 2048,
        "capabilities": {"reasoning_efforts": ["low", "high"]}} for name, endpoint, window in (("first", "one", 100000), ("second", "two", 200000))}}},
}
setting.data["custom_llms"] = {"runtime-test": ["first", "second"]}
setting.save()
database.close()


def wait_for(service, status):
    for _ in range(200):
        value = service.get_task("mutable_task")
        if value["task"]["status"] == status and (status not in {"WAITING_FOR_USER", "WAITING_FOR_APPROVAL"} or value["state"].get("pendingInteraction")):
            return value
        if value["task"]["status"] == "FAILED":
            raise AssertionError({"unexpected_status": "FAILED", "events": [(item.get("kind"), item.get("error_code")) for item in value["timeline"]]})
        time.sleep(0.05)
    raise AssertionError({"wanted": status, "actual": value["task"]["status"], "sync_error": value["sync_error"]})


service = TaskAgentService(workspace)
try:
    service.save_profile({"agent_id": "general", "name": "Mutable General", "instructions": "", "permission_mode": "full", "allow_shell": True,
        "allow_sub_agents": False, "allow_file_writes": False, "workflow_ids": [], "max_cycles": 0})
    service.create_task({"input_id": "mutable_task", "turn_input_id": "first_turn", "goal": "Ask a question, then verify the next operation requires approval.",
        "agent_id": "general", "model_provider": "Local", "model": "first", "reasoning_effort": "high"})
    detail = wait_for(service, "WAITING_FOR_USER")
    original_snapshot = detail["task"]["config_snapshot"]["agent_profile"]
    question = detail["state"]["pendingInteraction"]
    changed = service.update_runtime_settings({"task_id": "mutable_task", "request_id": "policy_change", "expected_revision": 0, "permission_mode": "ask"})
    assert changed["runtime_settings"]["permission_mode"] == "ask"
    switched = service.update_runtime_settings({"task_id": "mutable_task", "request_id": "model_change", "expected_revision": 1,
        "model_provider": "Local", "model": "second", "reasoning_effort": "low"})
    assert switched["runtime_settings"]["model"] == "second"
    assert switched["task"]["config_snapshot"]["agent_profile"] == original_snapshot
    target = {key: question[key] for key in ("sessionId", "turnId", "generation", "interactionId", "operationId", "attempt", "requestDigest")}
    service.act({"task_id": "mutable_task", "turn_id": detail["task"]["current_turn_id"], "action_id": "answer_question",
        "action": {"kind": "respond", "target": target, "answer": {"kind": "text", "text": "Continue"}}})
    approval = wait_for(service, "WAITING_FOR_APPROVAL")
    pending = approval["state"]["pendingInteraction"]
    service.update_runtime_settings({"task_id": "mutable_task", "request_id": "back_to_full", "expected_revision": 2, "permission_mode": "full"})
    still_pending = service.get_task("mutable_task")
    assert still_pending["state"]["pendingInteraction"]["requestId"] == pending["requestId"]
    service.approve({"task_id": "mutable_task", "turn_id": approval["task"]["current_turn_id"], "request_id": pending["requestId"], "decision": "deny"})
    wait_for(service, "COMPLETED")
    service.stop()

    service = TaskAgentService(workspace)
    restored = service.get_task("mutable_task")
    assert restored["runtime_settings"]["model"] == "second"
    assert restored["runtime_settings"]["permission_mode"] == "full"
    for index in range(7):
        service.send_message({"task_id": "mutable_task", "input_id": f"follow_up_{index}", "text": f"Provide the next brief update, number {index}."})
        wait_for(service, "COMPLETED")
    context = service.task_context({"task_id": "mutable_task"})
    assert context["context"]["limits"]["contextWindow"] == 200000
    assert context["token_usage"]["input_tokens"] > 0
    assert context["token_usage"]["cache_read_tokens"] is not None
    request = {"task_id": "mutable_task", "action_id": "compact_once", "expected_context_version": context["context"]["contextVersion"]}
    accepted = service.compact_context(request)
    assert accepted["compaction"]["accepted"] is True
    assert service.compact_context(request) == accepted
    for _ in range(200):
        compacted = service.task_context({"task_id": "mutable_task"})
        if compacted["compaction"] and compacted["compaction"]["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)
    assert compacted["compaction"]["status"] == "completed", compacted["compaction"]
    assert compacted["context"]["estimates"]["total"] < context["context"]["estimates"]["total"]
    assert "synthetic-runtime-test-key" not in json.dumps(service.get_task("mutable_task", cached=True))
    print(json.dumps({"passed": True, "same_task_model_switched": True, "full_to_ask_enforced": True, "pending_approval_preserved": True,
        "settings_survive_restart": True, "context_window": compacted["context"]["limits"]["contextWindow"],
        "native_compaction": compacted["compaction"]["status"], "usage": compacted["token_usage"]}))
finally:
    service.stop()
