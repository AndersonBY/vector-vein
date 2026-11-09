import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["VECTORVEIN_OUTPUT_DIR"] = str(Path.cwd() / "exports")
from models import WorkflowRunRecord, create_tables
from celery_worker import app
from utilities.config import cache
from task_agent.store import BusinessStore, now
from task_agent.workflows import WorkflowProvider, workflow_descriptor, workflow_run_views, resume_workflow, selected_workflows
from task_agent_workflow_fixture import create_workflow
from vv_agent.session.providers import Accepted, Definitive, Unknown

create_tables()
app.conf.update(task_always_eager=True, task_eager_propagates=True)
root = Path.cwd() / "data" / "task-agent"
store = BusinessStore(root / "tasks.db")
timestamp = now()
store.create_task(dict(tid="task", thread_id="task", title="test", goal="test", status="PROCESSING", current_turn_id="task/turn/start",
                       model_provider="local", model="test", reasoning_effort="default", config_snapshot={}, created_at=timestamp, updated_at=timestamp))
workspace = root / "workspaces" / "task"
workspace.mkdir(parents=True)
workflow = create_workflow()
descriptor = workflow_descriptor(workflow)
assert descriptor["parameters"]["required"] == ["text"]
assert selected_workflows([workflow.wid.hex])[0] == descriptor
try:
    selected_workflows([workflow.wid.hex, str(workflow.wid)])
except ValueError:
    pass
else:
    raise AssertionError("Duplicate canonical workflow IDs must be rejected")
provider = WorkflowProvider(root, "task", workspace, descriptor)

def plan(name, text="Synthetic report"):
    return SimpleNamespace(operation_id=name, attempt=1, turn_id="task/turn/start", payload={"request_digest": "a" * 64,
        "provider_binding": descriptor["tool_name"], "request": {"id": name, "name": descriptor["tool_name"], "arguments": {"text": text}}})

context = SimpleNamespace(resolve_workspace_path=lambda p: workspace / p)
first = provider.submit(plan("op1"), context=context)
assert isinstance(first, Accepted), first
run_id = first.handle["job_id"]
job = store.workflow_job(run_id)
record = WorkflowRunRecord.get_by_id(job["run_id"])
assert record.status == "PAUSED", record.status
assert record.data["pending_feedback_nodes"] == ["review"]
assert isinstance(provider.submit(plan("op1"), context=context), Accepted)
assert WorkflowRunRecord.select().count() == 1
assert isinstance(provider.query({**first.handle, "evidence": "forged"}), Unknown)
view = workflow_run_views(store, "task")[0]
feedback = view["feedback"][0]
assert "Synthetic report" in feedback["questions"][0]["prompt"]
reply = {"run_id": job["run_id"], "generation": feedback["generation"], "action_id": "reply1", "answers": [{"node_id": "review", "content": "Reviewed report"}]}
assert resume_workflow(store, "task", reply)["status"] == 200
assert resume_workflow(store, "task", reply)["status"] == 200
assert resume_workflow(store, "task", {**reply, "answers": [{"node_id": "review", "content": "different"}]})["status"] == 409
finished = provider.query(first.handle)
assert isinstance(finished, Definitive), finished
result = json.loads(finished.result["content"])
assert result["status"] == "FINISHED", result
assert result["files"] and (workspace / result["files"][0]["path"]).read_text(encoding="utf-8") == "Reviewed report"
assert WorkflowRunRecord.select().count() == 1
assert len(list((Path.cwd() / "exports").glob("*.md"))) == 1
restored = WorkflowProvider(root, "task", workspace, descriptor)
assert restored.query(first.handle).result == finished.result
assert restored.authenticate(None, None) is False

second = provider.submit(plan("op2"), context=context)
assert isinstance(second, Accepted)
stopped = provider.cancel(second.handle)
assert isinstance(stopped, Definitive) and json.loads(stopped.result["content"])["status"] == "STOPPED"
assert WorkflowRunRecord.select().count() == 2

# A publish exception must never create or dispatch a second run on retry.
with patch("celery_tasks.run_workflow.delay", side_effect=RuntimeError("lost publish acknowledgment")) as publish:
    uncertain = provider.submit(plan("op3"), context=context)
    assert isinstance(uncertain, Accepted)
    assert isinstance(provider.submit(plan("op3"), context=context), Accepted)
    assert publish.call_count == 1
    assert next(run for run in workflow_run_views(store, "task") if run["job_id"] == uncertain.handle["job_id"])["status"] == "UNKNOWN"
assert WorkflowRunRecord.select().count() == 3
uncertain_job = store.workflow_job(uncertain.handle["job_id"])
changed_record = WorkflowRunRecord.get_by_id(uncertain_job["run_id"])
changed_record.data["_task_agent_submission"] = "different-owner"
changed_record.save()
assert isinstance(provider.cancel(uncertain.handle), Unknown)
assert WorkflowRunRecord.get_by_id(changed_record.rid).status == "RUNNING"
changed_record.data["_task_agent_submission"] = uncertain_job["job_id"]
changed_record.save()
provider.cancel(uncertain.handle)

# Changing a definition after task creation is a definitive rejection before dispatch.
workflow.data = {**deepcopy(workflow.data), "changed": True}
workflow.save()
changed = provider.submit(plan("op4"), context=context)
assert isinstance(changed, Definitive) and changed.result["error_code"] == "workflow_changed"
assert WorkflowRunRecord.select().count() == 3

# Stop remains unresolved while an admitted worker is still active.
workflow.data.pop("changed")
workflow.save()
with patch("celery_tasks.run_workflow.delay"):
    running = provider.submit(plan("op5"), context=context)
    running_job = store.workflow_job(running.handle["job_id"])
    cache.set(f"workflow:record:{running_job['run_id']}:stop:active", 1)
    assert isinstance(provider.cancel(running.handle), Accepted)
    assert WorkflowRunRecord.get_by_id(running_job["run_id"]).status == "STOPPING"
print(json.dumps({"passed": True, "workflow_runs": WorkflowRunRecord.select().count(), "artifacts": len(result["files"])}))
