"""Exercise scheduled creation and continuation against the real local App Server."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

workspace = Path(sys.argv[1]).resolve()
port = int(sys.argv[2])
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.chdir(workspace)
os.environ.pop("VECTORVEIN_LLM_SETTINGS_FILE", None)

from cli import initialize  # noqa: E402
from models import Setting, database  # noqa: E402
from task_agent.service import TaskAgentService  # noqa: E402
from utilities import desktop_notifications  # noqa: E402

initialize()
setting = Setting.select().order_by(Setting.create_time.desc()).first()
setting.data["llm_settings"] = {
    "VERSION": "2",
    "endpoints": [{"id": "mock", "api_base": f"http://127.0.0.1:{port}/v1", "api_key": "local-test-credential"}],
    "backends": {"local": {"models": {"mock": {"id": "mock", "enabled": True, "endpoints": ["mock"],
        "function_call_available": False, "context_length": 32768, "max_output_tokens": 2048,
        "capabilities": {"reasoning_efforts": ["low", "max"]}}}}},
}
setting.data["custom_llms"] = {"test": ["mock"]}
setting.data["notifications"] = {"enabled": False, "language": "en-US"}
setting.save()
database.close()

notices = []
desktop_notifications.notify_task_finished = notices.append
service = TaskAgentService(workspace)


def execute(request_id):
    admitted = service.scheduler.run_now({"schedule_id": "daily", "input_id": request_id})
    service.scheduler.tick()
    for _ in range(120):
        detail = service.get_task(admitted["task_id"])
        if detail["task"]["status"] in {"COMPLETED", "FAILED", "INTERRUPTED"}:
            break
        time.sleep(0.2)
    assert detail["task"]["status"] == "COMPLETED", detail["task"]["status"]
    return detail


try:
    roots = [workspace / "source", workspace / "documents"]
    for root in roots:
        root.mkdir()
    service.save_project({"project_id": "project", "roots": [str(root) for root in roots]})
    saved = service.scheduler.save({"schedule_id": "daily", "goal": "请给出一句简短的完成摘要。", "agent_id": "general", "project_id": "project",
        "model_provider": "_local__test", "model": "mock", "reasoning_effort": "max", "run_mode": "continue", "permission_mode": "ask",
        "cron_expression": "0 9 * * *", "timezone": "Asia/Shanghai", "hide_after_run": True, "notify_after_run": False})
    first = execute("first")
    tid = first["task"]["tid"]
    assert first["task"]["hidden"] == 1
    assert first["task"]["config_snapshot"]["project"]["roots"] == [str(root) for root in roots]
    assert service.list_tasks()["tasks"] == []
    assert notices == []
    saved = service.scheduler.save({**saved, "expected_updated_at": saved["updated_at"], "reasoning_effort": "low", "hide_after_run": False, "notify_after_run": True})
    second = execute("second")
    assert second["task"]["tid"] == tid and len(second["messages"]) == 4
    assert second["runtime_settings"]["reasoning_effort"] == "low"
    assert second["task"]["hidden"] == 0
    assert notices == ["COMPLETED"]
    assert service.scheduler.get("daily")["last_run"]["status"] == "COMPLETED"
    saved = service.scheduler.save({**saved, "expected_updated_at": saved["updated_at"], "run_mode": "new", "project_id": None, "notify_after_run": False})
    third = execute("third")
    assert third["task"]["tid"] != tid and third["task"]["project_id"] is None
    assert len(third["messages"]) == 2
    assert service.scheduler.run_now({"schedule_id": "daily", "input_id": "third"})["task_id"] == third["task"]["tid"]
    saved = service.scheduler.save({**saved, "expected_updated_at": saved["updated_at"], "run_mode": "continue", "existing_task_id": tid, "project_id": "project"})
    fourth = execute("existing")
    assert fourth["task"]["tid"] == tid and len(fourth["messages"]) == 6
    assert "local-test-credential" not in json.dumps(service.scheduler.list())
finally:
    service.stop()

resumed = TaskAgentService(workspace)
try:
    assert len(resumed.list_tasks()["tasks"]) == 2
    assert resumed.scheduler.get("daily")["last_run"]["status"] == "COMPLETED"
    assert len(resumed.get_task(tid, cached=True)["messages"]) == 6
finally:
    resumed.stop()
print(json.dumps({"status": "COMPLETED", "tasks": 2, "notifications": len(notices), "model_calls": 4}))
