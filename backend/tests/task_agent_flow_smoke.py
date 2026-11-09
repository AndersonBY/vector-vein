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
from vv_agent.session.sqlite import SQLiteStore  # noqa: E402


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
                    "function_call_available": False,
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

service = TaskAgentService(workspace)
try:
    payload = {
        "input_id": "task_smoke",
        "turn_input_id": "turn_smoke",
        "goal": "整理一份两句话的交付摘要。",
        "attachments": [],
        "model_provider": "_local__local-test",
        "model": "mock-task-model",
        "reasoning_effort": "max",
    }
    detail = service.create_task(payload)
    for _ in range(50):
        detail = service.get_task("task_smoke")
        if detail["task"]["status"] in {"COMPLETED", "FAILED"}:
            break
        time.sleep(0.2)
    assert detail["task"]["status"] == "COMPLETED", detail
    assert len(detail["messages"]) == 2, detail
    assert "模拟交付" in detail["messages"][-1]["content"]
    assert "local-test-credential" not in json.dumps(detail["task"]["config_snapshot"])

    repeated = service.create_task(payload)
    assert len(repeated["messages"]) == 2
    service.send_message({"task_id": "task_smoke", "input_id": "turn_followup", "text": "再补充一句。"})
    for _ in range(50):
        detail = service.get_task("task_smoke")
        if detail["task"]["status"] == "COMPLETED" and len(detail["messages"]) == 4:
            break
        time.sleep(0.2)
    assert detail["task"]["status"] == "COMPLETED", detail
    assert len(detail["messages"]) == 4, detail
finally:
    service.stop()

resumed = TaskAgentService(workspace)
try:
    restored = resumed.get_task("task_smoke")
    assert restored["task"]["status"] == "COMPLETED", restored
    assert len(restored["messages"]) == 4, restored
    assert len(resumed.list_tasks()["tasks"]) == 1
    if '--delete' in sys.argv:
        # Exercise deletion with the App Server alive and its real session ledger populated.
        for _ in range(30):
            try:
                result = resumed.delete_task({'task_id': 'task_smoke', 'expected_updated_at': restored['task']['updated_at']})
                break
            except Exception as error:
                from task_agent.deletion import DeletionConflict
                if not isinstance(error, DeletionConflict) or error.code != 'engine_busy':
                    raise
                time.sleep(0.1)
        else:
            raise AssertionError('Execution engine never became idle')
        assert result['task_ids'] == ['task_smoke']
        assert resumed.list_tasks()['tasks'] == []
        try:
            resumed.get_task('task_smoke')
        except KeyError:
            pass
        else:
            raise AssertionError('Deleted task was restored from runtime cache')
    print(json.dumps({"status": restored["task"]["status"], "messages": len(restored["messages"])}, ensure_ascii=False))
finally:
    resumed.stop()

if '--delete' in sys.argv:
    with SQLiteStore.standalone(str(resumed.task_root / 'sessions.db')) as ledger:
        assert ledger.connection.execute('SELECT count(*) FROM sk_session').fetchone()[0] == 0
    restarted = TaskAgentService(workspace)
    try:
        restarted.status()
        assert restarted.list_tasks()['tasks'] == []
    finally:
        restarted.stop()
