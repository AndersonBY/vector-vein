import json
import os
import sys
import time
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["VECTORVEIN_OUTPUT_DIR"] = str(Path.cwd() / "exports")
from cli import initialize
from models import Setting, WorkflowRunRecord
from celery_worker import CeleryWorkerManager
from task_agent.service import TaskAgentService
from task_agent_workflow_fixture import create_workflow

initialize()
port = int(sys.argv[1])
setting = Setting.select().first()
setting.data["llm_settings"] = {"VERSION": "2", "endpoints": [{"id": "test", "api_key": "synthetic-key", "api_base": f"http://127.0.0.1:{port}/v1"}],
    "backends": {"local": {"models": {"mock": {"id": "mock", "enabled": True, "endpoints": ["test"], "function_call_available": True, "context_length": 32768, "max_output_tokens": 2048}}}}}
setting.data["llm_settings"]["backends"]["deepseek"] = deepcopy(setting.data["llm_settings"]["backends"]["local"])
setting.save()
workflow = create_workflow()
service = TaskAgentService(Path.cwd())
worker = CeleryWorkerManager(concurrency=1)
worker.start()
service.save_profile({"permission_mode": "ask", "agent_id": "wf", "name": "Workflow check", "instructions": "Call the workflow.", "workflow_ids": [workflow.wid.hex], "max_cycles": 5})

def start(tid):
    return service.create_task({"input_id": tid, "turn_input_id": "start", "goal": "Run the workflow", "agent_id": "wf", "model_provider": "local", "model": "mock"})


def wait(tid, status):
    for _ in range(120):
        detail = service.get_task(tid)
        if detail["task"]["status"] == status:
            return detail
        if detail["task"]["status"] == "FAILED":
            raise AssertionError(detail)
        time.sleep(0.2)
    raise AssertionError(detail)


def approve(tid, decision="allow"):
    detail = wait(tid, "WAITING_FOR_APPROVAL")
    pending = detail["state"]["pendingInteraction"]
    service.approve({"task_id": tid, "turn_id": detail["task"]["current_turn_id"], "request_id": pending["requestId"], "decision": decision})


try:
    start("success")
    approve("success")
    detail = wait("success", "WAITING_FOR_WORKFLOW")
    assert WorkflowRunRecord.select().count() == 1
    run = detail["workflow_runs"][0]
    service.stop()
    service = TaskAgentService(Path.cwd())
    detail = wait("success", "WAITING_FOR_WORKFLOW")
    assert detail["workflow_runs"][0]["run_id"] == run["run_id"]
    feedback = detail["workflow_runs"][0]["feedback"][0]
    payload = {"task_id": "success", "run_id": feedback["run_id"], "generation": feedback["generation"], "action_id": "feedback",
               "answers": [{"node_id": "review", "content": "Approved content"}]}
    service.workflow_feedback(payload)
    service.workflow_feedback(payload)
    detail = wait("success", "COMPLETED")
    assert detail["workflow_runs"][0]["status"] == "FINISHED"
    assert WorkflowRunRecord.select().count() == 1
    copies = list(service._task_workspace("success").rglob("*.md"))
    assert len(copies) == 1 and copies[0].read_text(encoding="utf-8") == "Approved content"

    start("denied")
    approve("denied", "deny")
    wait("denied", "COMPLETED")
    assert WorkflowRunRecord.select().count() == 1

    start("cancelled")
    approve("cancelled")
    detail = wait("cancelled", "WAITING_FOR_WORKFLOW")
    service.act({"task_id": "cancelled", "turn_id": detail["task"]["current_turn_id"], "action_id": "cancel", "action": {"kind": "cancel"}})
    detail = wait("cancelled", "INTERRUPTED")
    assert detail["workflow_runs"][0]["status"] == "STOPPED"
    Path("workflow-bridge-report.json").write_text(json.dumps({"passed": True, "runs": WorkflowRunRecord.select().count()}), encoding="utf-8")
finally:
    service.stop()
    worker.stop()
