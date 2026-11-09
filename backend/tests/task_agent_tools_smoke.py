"""Run a real desktop task flow against a local model endpoint."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


workspace = Path(sys.argv[1]).resolve()
port = int(sys.argv[2])
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.chdir(workspace)

from cli import initialize  # noqa: E402
from models import Setting, database  # noqa: E402
from task_agent.service import TaskAgentService  # noqa: E402


initialize()
setting = Setting.select().order_by(Setting.create_time.desc()).first()
setting.data["llm_settings"] = {
    "VERSION": "2",
    "endpoints": [{
        "id": "mock-endpoint",
        "api_base": f"http://127.0.0.1:{port}/v1",
        "api_key": "local-test-credential",
    }],
    "backends": {
        "local": {
            "models": {
                "mock-task-model": {
                    "id": "mock-task-model",
                    "enabled": True,
                    "endpoints": ["mock-endpoint"],
                    "function_call_available": True,
                    "context_length": 32768,
                    "max_output_tokens": 2048,
                    "supported_reasoning_efforts": ["low", "max"],
                    "capabilities": {"reasoning_efforts": ["low", "max"]},
                },
            },
        },
    },
}
setting.data["custom_llms"] = {"local-test": ["mock-task-model"]}
setting.data["model_preferences"] = {"default": {"model_provider": "_local__local-test", "model": "mock-task-model"}}
setting.save()
database.close()



def wait_for(service, expected, tid="tools"):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        detail = service.get_task(tid)
        if detail["task"]["status"] == expected:
            return detail
        assert detail["task"]["status"] not in {"FAILED", "INTERRUPTED", "COMPLETED"}, detail
        time.sleep(.1)
    raise AssertionError(detail)

service = TaskAgentService(workspace)
try:
    service.create_task({"input_id": "tools", "turn_input_id": "start", "goal": "Validate shell and delegation", "permission_mode": "full", "model_provider": "_local__local-test", "model": "mock-task-model"})
    detail = wait_for(service, "WAITING_FOR_USER")
    question = detail["state"]["pendingInteraction"]
    assert "/child/" in question["sessionId"], question
finally:
    service.stop()

service = TaskAgentService(workspace)
try:
    detail = service.get_task("tools")
    assert detail["state"]["pendingInteraction"] == question
    target = {key: question[key] for key in ("sessionId", "turnId", "generation", "interactionId", "operationId", "attempt", "requestDigest")}
    service.act({"task_id": "tools", "turn_id": detail["task"]["current_turn_id"], "action_id": "answer-child", "action": {"kind": "respond", "target": target, "answer": {"kind": "single", "selected": ["Yes"], "custom": []}}})
    detail = wait_for(service, "COMPLETED")
    errors = [i for i in detail["timeline"] if i.get("kind") == "tool" and i.get("status") == "error"]
    assert not errors, errors
    children = [i for i in detail["timeline"] if i["kind"] == "sub_agent"]
    assert len(children) == 3, detail
    assert all(i["status"] == "completed" for i in children), children
    for name in ("gated", "batch-a", "batch-b"):
        assert (service._task_workspace("tools") / f"outputs/{name}.txt").read_text() == "child verified"
    service.save_profile({"agent_id": "restricted", "name": "Read only", "instructions": "Only read files", "allow_shell": False, "allow_sub_agents": True, "allow_file_writes": False})
    service.create_task({"input_id": "restricted", "turn_input_id": "start", "goal": "RESTRICTED permission test", "agent_id": "restricted", "model_provider": "_local__local-test", "model": "mock-task-model"})
    restricted = wait_for(service, "COMPLETED", "restricted")
    assert not (service._task_workspace("restricted") / "outputs/batch-b.txt").exists()
    assert restricted["task"]["config_snapshot"]["command_shell"] == {}
    service.create_task({"input_id": "cancel", "turn_input_id": "start", "goal": "CANCEL_CHILDREN", "model_provider": "_local__local-test", "model": "mock-task-model"})
    cancelling = wait_for(service, "WAITING_FOR_USER", "cancel")
    child_ids = [e["child_session_id"] for e in cancelling["timeline"] if e["kind"] == "sub_agent"]
    assert len(child_ids) == 2
    service.act({"task_id": "cancel", "turn_id": cancelling["task"]["current_turn_id"], "action_id": "cancel-children", "action": {"kind": "cancel"}})
    cancelled = wait_for(service, "INTERRUPTED", "cancel")
    assert cancelled["state"]["pendingInteraction"] is None
    from vv_agent.session.sqlite import SQLiteStore
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        with SQLiteStore.standalone(str(service.task_root / "sessions.db")) as store:
            states = [store.read_state(child_id)[0] for child_id in child_ids]
        if all(state.active_turn_id is None for state in states):
            break
        service.get_task("cancel")
        time.sleep(.1)
    assert all(state.active_turn_id is None for state in states)
    if os.name == "nt":
        from ctypes import wintypes as W
        from task_agent.windows_job import bind, Wait, CloseHandle
        service.create_task({"input_id": "cancel_shell", "turn_input_id": "start", "goal": "CANCEL_SHELL", "permission_mode": "full", "model_provider": "_local__local-test", "model": "mock-task-model"})
        shell_wait = wait_for(service, "WAITING_FOR_USER", "cancel_shell")
        pid_file = service._task_workspace("cancel_shell") / "command.pid"
        deadline = time.monotonic() + 8
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        handle = bind("OpenProcess", W.HANDLE, W.DWORD, W.BOOL, W.DWORD)(0x100000, False, int(pid_file.read_text()))
        assert handle and Wait(handle, 0) == 258
        try:
            service.act({"task_id": "cancel_shell", "turn_id": shell_wait["task"]["current_turn_id"], "action_id": "stop-command", "action": {"kind": "cancel"}})
            wait_for(service, "INTERRUPTED", "cancel_shell")
            assert Wait(handle, 5000) == 0, "Cancelling the task did not terminate its background command"
        finally:
            CloseHandle(handle)
    print(json.dumps({"status": detail["task"]["status"], "children": len(children), "restart": True}))
finally:
    service.stop()
