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
setting.data["llm_settings"]["backends"]["local"]["models"]["risk-review"] = {"id": "risk-model", "enabled": True, "endpoints": ["mock-endpoint"], "function_call_available": False}
setting.data["task_agent_approval"] = {"model_provider": "local", "model": "risk-review"}
setting.save()
database.close()




report = {}
service = TaskAgentService(workspace)
try:
    for mode in ("ask", "auto", "full"):
        target = workspace / f"outside-{mode}.txt"
        payload = {"input_id": mode, "turn_input_id": "start", "goal": "TARGET=" + str(target), "permission_mode": mode, "model_provider": "_local__local-test", "model": "mock-task-model"}
        service.create_task(payload)
        seen = set()
        deadline = time.monotonic() + 65
        while time.monotonic() < deadline:
            detail = service.get_task(mode)
            question = detail["state"].get("pendingInteraction")
            if question and question["kind"] == "approval" and question["requestId"] not in seen and (mode != "auto" or (question.get("risk_review") or {}).get("status") == "manual"):
                seen.add(question["requestId"])
                if "/child/" in question["sessionId"]:
                    assert not target.exists()
                    assert question["tool_name"] == "write_file", question
                    assert question["arguments"]["path"] == str(target), question
                    if mode == "ask":
                        service.stop()
                        service = TaskAgentService(workspace)
                        restored = service.get_task(mode)["state"]["pendingInteraction"]
                        assert restored == question
                    decision = "allow"
                else:
                    assert not (service._task_workspace(mode) / "outputs/command.txt").exists()
                    decision = "deny"
                service.approve({"task_id": mode, "turn_id": detail["task"]["current_turn_id"], "request_id": question["requestId"], "decision": decision})
            if detail["task"]["status"] == "COMPLETED":
                break
            assert detail["task"]["status"] not in {"FAILED", "INTERRUPTED"}, detail
            time.sleep(.1)
        assert detail["task"]["status"] == "COMPLETED", detail
        assert target.read_text() == "approved-child"
        shell_file = service._task_workspace(mode) / "outputs/command.txt"
        assert shell_file.exists() == (mode == "full")
        report[mode] = len(seen)
        from task_agent.service import TaskConflict
        try:
            service.create_task({**payload, "permission_mode": "ask" if mode == "full" else "full"})
        except TaskConflict:
            pass
        else:
            raise AssertionError("Retry changed frozen permissions")
    print(json.dumps(report))
finally:
    service.stop()
