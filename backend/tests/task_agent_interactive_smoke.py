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

from task_agent.files import list_files, preview_file  # noqa: E402


def wait_for(service, expected, tid="interactive"):
    for _ in range(150):
        detail = service.get_task(tid)
        if detail["task"]["status"] == expected:
            return detail
        if detail["task"]["status"] in {"FAILED", "INTERRUPTED"}:
            raise AssertionError(detail)
        time.sleep(0.1)
    raise AssertionError(detail)


service = TaskAgentService(workspace)
try:
    service.save_profile({"permission_mode": "ask", "agent_id": "writer", "name": "交付助手", "instructions": "先确认格式，再生成报告。", "max_cycles": 30})
    service.create_task({"input_id": "interactive", "turn_input_id": "start", "goal": "生成一份验收报告", "agent_id": "writer",
                         "model_provider": "_local__local-test", "model": "mock-task-model"})
    detail = wait_for(service, "WAITING_FOR_USER")
    assert detail["todos"][0]["title"] == "确认交付格式", detail
    assert any(item["kind"] == "tool" and item["tool_name"] == "todo_write" for item in detail["timeline"])
    question = detail["state"]["pendingInteraction"]
    assert question["answerSpec"]["options"] == ["Markdown", "纯文本"]
    timestamp = detail["task"]["updated_at"]
    assert service.get_task("interactive")["task"]["updated_at"] == timestamp
    service.save_profile({"permission_mode": "ask", "agent_id": "writer", "name": "changed", "instructions": "changed", "max_cycles": 5})
    assert detail["task"]["config_snapshot"]["agent_profile"]["name"] == "交付助手"
finally:
    service.stop()

service = TaskAgentService(workspace)
try:
    detail = service.get_task("interactive")
    assert detail["state"]["pendingInteraction"] == question
    target = {key: question[key] for key in ("sessionId", "turnId", "generation", "interactionId", "operationId", "attempt", "requestDigest")}
    response = {"task_id": "interactive", "turn_id": detail["task"]["current_turn_id"], "action_id": "answer",
                "action": {"kind": "respond", "target": target, "answer": {"kind": "single", "selected": ["Markdown"], "custom": []}}}
    service.act(response)
    detail = wait_for(service, "COMPLETED")
    assert all(todo["status"] == "completed" for todo in detail["todos"]), detail
    assert len([item for item in detail["timeline"] if item["kind"] == "tool"]) == 4, detail
    assert len([item for item in detail["timeline"] if item["kind"] == "assistant"]) >= 4, detail
    assert list_files(service, "interactive")["files"][0]["path"] == "outputs/验收报告.md"
    assert "已确认交付格式" in preview_file(service, "interactive", "outputs/验收报告.md")["text"]
    completed = next(item for item in detail["timeline"] if item.get("tool_name") == "write_file")
    result = service.read_tool_result({"task_id": "interactive", "event_id": completed["result_event_id"]})
    assert result["eof"] is True
    original_events = len(service.store.events("interactive"))
    service.act(response)
    assert len(service.store.events("interactive")) == original_events
    assert len([m for m in service.store.list_messages("interactive") if m["content"] == "Markdown"]) == 1
finally:
    service.stop()

service = TaskAgentService(workspace)
try:
    restored = service.get_task("interactive")
    assert restored["task"]["status"] == "COMPLETED", restored
    assert len(service.store.events("interactive")) == original_events
    assert all(todo["status"] == "completed" for todo in restored["todos"])
    detail = service.create_task({"input_id": "controls", "turn_input_id": "start", "goal": "测试暂停和停止", "model_provider": "_local__local-test", "model": "mock-task-model"})
    turn_id = detail["task"]["current_turn_id"]
    service.act({"task_id": "controls", "turn_id": turn_id, "action_id": "pause", "action": {"kind": "suspend"}})
    wait_for(service, "PAUSED", "controls")
    service.act({"task_id": "controls", "turn_id": turn_id, "action_id": "resume", "action": {"kind": "resume"}})
    wait_for(service, "WAITING_FOR_USER", "controls")
    service.act({"task_id": "controls", "turn_id": turn_id, "action_id": "cancel", "action": {"kind": "cancel"}})
    for _ in range(100):
        cancelled = service.get_task("controls")
        if cancelled["task"]["status"] == "INTERRUPTED":
            break
        time.sleep(0.1)
    assert cancelled["task"]["status"] == "INTERRUPTED", cancelled
    print(json.dumps({"status": restored["task"]["status"], "events": original_events, "file": "outputs/验收报告.md"}, ensure_ascii=False))
finally:
    service.stop()
