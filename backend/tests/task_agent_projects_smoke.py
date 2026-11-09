"""Native App Server acceptance for multi-root Project tasks and inherited child access."""

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
from models import Setting  # noqa: E402
from task_agent.service import TaskAgentService  # noqa: E402

initialize()
setting = Setting.select().order_by(Setting.create_time.desc()).first()
setting.data["llm_settings"] = {
    "VERSION": "2",
    "endpoints": [
        {
            "id": "mock",
            "api_base": f"http://127.0.0.1:{port}/v1",
            "api_key": "synthetic-local-key",
        }
    ],
    "backends": {
        "local": {
            "models": {
                "mock-task-model": {
                    "id": "mock-task-model",
                    "enabled": True,
                    "endpoints": ["mock"],
                    "function_call_available": True,
                    "context_length": 32768,
                    "max_output_tokens": 2048,
                }
            }
        }
    },
}
setting.data["custom_llms"] = {"project-test": ["mock-task-model"]}
setting.save()
primary = workspace / "source one" / "app"
secondary = workspace / "source two" / "app"
primary.mkdir(parents=True)
secondary.mkdir(parents=True)
(primary / "keep.txt").write_text("primary-existing")
(secondary / "keep.txt").write_text("secondary-existing")
service = TaskAgentService(workspace, data_path=workspace / "data")


def wait_for(status):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        detail = service.get_task("project-task")
        if detail["task"]["status"] == status:
            return detail
        if detail["task"]["status"] == "FAILED":
            raise AssertionError(detail)
        time.sleep(0.1)
    raise AssertionError(detail)


try:
    project = service.save_project(
        {"project_id": "project", "name": "", "roots": [str(primary), str(secondary)]}
    )
    assert project["name"] == "app"
    service.create_task(
        {
            "input_id": "project-task",
            "goal": "Project acceptance\nSECONDARY=" + str(secondary),
            "project_id": "project",
            "permission_mode": "ask",
            "model_provider": "_local__project-test",
            "model": "mock-task-model",
        }
    )
    detail = wait_for("WAITING_FOR_APPROVAL")
    pending = detail["state"]["pendingInteraction"]
    approval = next(
        entry
        for entry in detail["timeline"]
        if entry["kind"] == "approval_requested"
        and entry["request_id"] == pending["requestId"]
    )
    assert approval["tool_name"] == "bash", approval
    assert (primary / "primary.txt").read_text() == "primary-result"
    assert (secondary / "child.txt").read_text() == "child-result"
    service.approve(
        {
            "task_id": "project-task",
            "turn_id": detail["task"]["current_turn_id"],
            "request_id": pending["requestId"],
            "decision": "allow",
        }
    )
    detail = wait_for("COMPLETED")
    assert (secondary / "shell.txt").read_text() == "secondary-shell"
    assert (primary / "keep.txt").read_text() == "primary-existing"
    assert (secondary / "keep.txt").read_text() == "secondary-existing"
    assert not (service.task_root / "workspaces" / "project-task").exists()
    service.save_project(
        {
            "project_id": "project",
            "roots": [str(secondary)],
            "expected_updated_at": project["updated_at"],
        }
    )
    service.stop()
    service = TaskAgentService(workspace, data_path=workspace / "data")
    assert service._task_workspace("project-task") == primary
    service.send_message(
        {"task_id": "project-task", "input_id": "follow", "text": "FOLLOWUP"}
    )
    wait_for("COMPLETED")
    assert service.store.get_task("project-task")["config_snapshot"]["project"][
        "roots"
    ] == [str(primary), str(secondary)]
    print(
        json.dumps(
            {
                "completed": True,
                "child_secondary": True,
                "shell_secondary": True,
                "restart": True,
            }
        )
    )
finally:
    service.stop()
