import json
from types import SimpleNamespace

import pytest

from task_agent.files import list_files, preview_file, workspace_file
from task_agent.host import DesktopTaskAgentHost
from task_agent.permissions import requires_approval
from task_agent.projects import ProjectError
from task_agent.service import TaskAgentService, TaskConflict
from task_agent.store import BusinessStore


class Process:
    def __init__(self):
        self.calls = []

    def start(self):
        return {"connected": True}

    def request(self, method, params):
        self.calls.append((method, params))
        return {"turnId": params.get("threadId", "") + "/turn/" + params["inputId"]}

    def stop(self):
        pass


@pytest.fixture
def service(tmp_path, monkeypatch):
    result = TaskAgentService(tmp_path, process=Process(), data_path=tmp_path / "state")
    monkeypatch.setattr(
        "task_agent.service.build_model_snapshot",
        lambda *args: {"endpoint_options": [{}]},
    )
    monkeypatch.setattr("task_agent.service.current_llm_settings", lambda: {})
    monkeypatch.setattr(
        result, "get_task", lambda tid: {"task": result.store.get_task(tid)}
    )
    monkeypatch.setattr(result, "_start_watching", lambda: None)
    monkeypatch.setattr("task_agent.workflows.selected_workflows", lambda ids: [])
    yield result
    result.stop()


def folders(tmp_path):
    roots = [tmp_path / "前端 folder", tmp_path / "后端 folder"]
    for root in roots:
        root.mkdir()
    return roots


def create(service, tid, project_id=None):
    return service.create_task(
        {
            "input_id": tid,
            "goal": "Synthetic project task",
            "model_provider": "mock",
            "model": "mock",
            "project_id": project_id,
        }
    )["task"]


def test_project_defaults_deduplication_and_optimistic_updates(tmp_path, service):
    a, b = folders(tmp_path)
    project = service.save_project(
        {"project_id": "p", "name": " ", "roots": [str(a), str(a / "."), str(b)]}
    )
    assert project["name"] == a.name and project["roots"] == [str(a), str(b)]
    assert all(folder["available"] for folder in project["folders"])
    assert not list(a.iterdir()) and not list(b.iterdir())
    assert (
        service.save_project(
            {"project_id": "p", "name": "", "roots": project["roots"]}
        )["updated_at"]
        == project["updated_at"]
    )
    changed = service.save_project(
        {
            "project_id": "p",
            "name": "Changed",
            "roots": [str(b), str(a)],
            "expected_updated_at": project["updated_at"],
        }
    )
    with pytest.raises(TaskConflict):
        service.save_project(
            {
                "project_id": "p",
                "name": "Stale",
                "roots": [str(a)],
                "expected_updated_at": project["updated_at"],
            }
        )
    assert service.get_project("p")["name"] == changed["name"]


@pytest.mark.parametrize("roots", [[], ["relative"], [""], ["missing:/folder"]])
def test_invalid_project_folders_rejected(service, roots):
    with pytest.raises(ProjectError):
        service.save_project({"project_id": "p", "roots": roots})
    assert service.list_projects() == []


def test_project_task_uses_real_primary_and_freezes_both_roots(tmp_path, service):
    a, b = folders(tmp_path)
    project = service.save_project({"project_id": "p", "roots": [str(a), str(b)]})
    task = create(service, "one", "p")
    assert task["project_id"] == "p"
    assert service._task_workspace("one") == a
    assert service.process.calls[0][1]["cwd"] == str(a)
    assert not (service.task_root / "workspaces" / "one").exists()
    service.save_project(
        {
            "project_id": "p",
            "name": "new",
            "roots": [str(b)],
            "expected_updated_at": project["updated_at"],
        }
    )
    assert service._task_workspace("one") == a
    assert task["config_snapshot"]["project"]["roots"] == [str(a), str(b)]
    assert create(service, "two", "p")["config_snapshot"]["project"]["roots"] == [
        str(b)
    ]
    service.retry_start("one")
    with pytest.raises(TaskConflict):
        create(service, "one")
    create(service, "standalone")
    assert [t["tid"] for t in service.store.list_tasks(1, "p")] == ["two"]
    assert [t["tid"] for t in service.store.list_tasks(1, "p", 1)] == ["one"]
    assert service.store.list_tasks(1, "p", 2) == []
    assert service.list_projects()[0]["task_count"] == 2
    restored = BusinessStore(service.store.path)
    assert restored.get_task("one")["config_snapshot"]["project"]["roots"] == [
        str(a),
        str(b),
    ]


def test_host_rejects_forged_project_roots_and_wrong_cwd(tmp_path, service):
    a, b = folders(tmp_path)
    service.save_project({"project_id": "p", "roots": [str(a), str(b)]})
    task = create(service, "task", "p")
    host = DesktopTaskAgentHost(service.task_root)
    params = {
        "agentKey": "desktop-task",
        "inputId": "task",
        "cwd": str(a),
        "metadata": {"model_snapshot": task["config_snapshot"]},
    }
    assert host.authorize("test", "thread/start", params)
    assert not host.authorize("test", "thread/start", {**params, "cwd": str(b)})
    forged = json.loads(json.dumps(params))
    forged["metadata"]["model_snapshot"]["project"]["roots"].append(str(tmp_path))
    assert not host.authorize("test", "thread/start", forged)
    b.rmdir()
    with pytest.raises(ProjectError):
        host._workspace("task", str(a))
    assert not b.exists()


def test_files_and_approval_use_explicit_roots_not_common_parent(tmp_path, service):
    a, b = folders(tmp_path)
    service.save_project({"project_id": "p", "roots": [str(a), str(b)]})
    create(service, "task", "p")
    (a / "same.txt").write_text("first")
    (b / "same.txt").write_text("second")
    (tmp_path / "outside.txt").write_text("outside")
    assert preview_file(service, "task", "project-files/0/same.txt")["text"] == "first"
    assert preview_file(service, "task", "project-files/1/same.txt")["text"] == "second"
    assert (
        list_files(service, "task", "1")["files"][0]["path"]
        == "project-files/1/same.txt"
    )
    for path in (
        "../outside.txt",
        str(tmp_path / "outside.txt"),
        "project-files/1/../outside.txt",
        "project-files/99/same.txt",
        "project-files/1/.vv-agent/secret",
    ):
        with pytest.raises(ValueError):
            workspace_file(service, "task", path)
    context = SimpleNamespace(
        workspace=a, task_metadata={"workspace_roots": [str(a), str(b)]}
    )
    assert not requires_approval(
        "ask", "write_file", context, {"path": str(b / "new.txt")}
    )
    assert requires_approval(
        "auto", "write_file", context, {"path": str(b / "new.txt")}
    )
    assert requires_approval("ask", "read_file", context, {"path": "../outside.txt"})
    assert requires_approval(
        "ask", "bash", context, {"command": "pwd", "exec_dir": str(b)}
    )
    (b / "same.txt").unlink()
    b.rmdir()
    assert preview_file(service, "task", "project-files/0/same.txt")["text"] == "first"
    assert not service.get_project("p")["folders"][1]["available"]


def test_project_attachments_get_task_specific_paths_without_overwrites(
    tmp_path, service
):
    a, b = folders(tmp_path)
    source = b / "input.txt"
    source.write_text("attached")
    service.save_project({"project_id": "p", "roots": [str(a), str(b)]})
    service.create_task(
        {
            "input_id": "task",
            "goal": "use attachment",
            "model": "mock",
            "project_id": "p",
            "attachments": [str(source)],
        }
    )
    attachment = service.store.list_messages("task")[0]["attachments"][0]
    assert attachment["path"] == "inputs/task/input.txt"
    assert (a / attachment["path"]).read_text() == "attached"
    assert source.read_text() == "attached"


@pytest.mark.parametrize("project_id", [False, 0, [], {}])
def test_malformed_project_identity_does_not_fall_back_to_standalone(service, project_id):
    with pytest.raises(ValueError):
        create(service, "bad", project_id)
    with pytest.raises(ValueError):
        service.list_tasks(project_id=project_id)
    assert service.store.get_task("bad") is None


def test_project_workspace_browses_both_roots_before_any_task_exists(tmp_path, service, monkeypatch):
    from api import task_agent_api
    a, b = folders(tmp_path)
    (a / "report.md").write_text("# Primary", encoding="utf-8")
    (b / "report.md").write_text("# Secondary", encoding="utf-8")
    (b / "App.vue").write_text("<template>Source preview</template>", encoding="utf-8")
    (b / "example.ps1").write_text("Write-Output 'source only'", encoding="utf-8")
    service.save_project({"project_id": "p", "roots": [str(a), str(b)]})
    monkeypatch.setattr(task_agent_api, "task_agent_service", lambda: service)
    api = task_agent_api.TaskAgentAPI()
    for root_id, expected in (("0", "# Primary"), ("1", "# Secondary")):
        listing = api.project_files({"project_id": "p", "root_id": root_id})
        assert listing["status"] == 200
        assert len(listing["data"]["roots"]) == 2
        reference = f"project-files/{root_id}/report.md"
        assert reference in {file["path"] for file in listing["data"]["files"]}
        preview = api.project_preview_file({"project_id": "p", "path": reference})
        assert preview["data"]["text"] == expected
        assert preview["data"]["markdown"] is True
    source = api.project_preview_file({"project_id": "p", "path": "project-files/1/App.vue"})
    assert source["data"]["text"] == "<template>Source preview</template>"
    assert source["data"]["markdown"] is False
    assert api.project_open_file({"project_id": "p", "path": "project-files/1/example.ps1"})["status"] == 400
    assert service.store.list_tasks() == []
    assert service.process.calls == []
    for path in ("project-files/0/../private.txt", "project-files/2/report.md", "project-files/0/.VV-AGENT/secret", "project-files/0/report.md:ads", str(tmp_path / "outside.txt")):
        assert api.project_preview_file({"project_id": "p", "path": path})["status"] == 400
    assert api.project_files({"project_id": "missing"})["status"] == 404
    assert api.project_files({})["status"] == 400


def test_project_browser_uses_current_roots_while_task_browser_keeps_snapshot(tmp_path, service):
    a, b = folders(tmp_path)
    (a / "same.txt").write_text("original")
    (b / "same.txt").write_text("new primary")
    project = service.save_project({"project_id": "p", "roots": [str(a), str(b)]})
    create(service, "task", "p")
    service.save_project({"project_id": "p", "roots": [str(b)], "expected_updated_at": project["updated_at"]})
    assert preview_file(service, None, "project-files/0/same.txt", project_id="p")["text"] == "new primary"
    assert preview_file(service, "task", "project-files/0/same.txt")["text"] == "original"
    with pytest.raises(ValueError):
        preview_file(service, "task", "same.txt", project_id="p")


def test_project_search_filters_all_titles_and_goals_before_pagination(tmp_path, service):
    a, b = folders(tmp_path)
    service.save_project({"project_id": "p", "roots": [str(a)]})
    service.save_project({"project_id": "other", "roots": [str(b)]})
    create(service, "older-title", "p")
    service.store.update_task("older-title", title="Report 旧任务", goal="original")
    create(service, "older-goal", "p")
    service.store.update_task("older-goal", title="另一个任务", goal="REPORT 数据核对")
    for index in range(8):
        create(service, f"recent-{index}", "p")
    create(service, "other-project", "other")
    service.store.update_task("other-project", title="Report 外部项目")
    assert all(task["tid"].startswith("recent-") for task in service.list_tasks(6, "p")["tasks"])
    assert [task["tid"] for task in service.list_tasks(1, "p", search=" report ")["tasks"]] == ["older-goal"]
    assert [task["tid"] for task in service.list_tasks(1, "p", 1, "report")["tasks"]] == ["older-title"]
    assert service.list_tasks(1, "p", 2, "report")["tasks"] == []
    assert service.list_tasks(20, "p", search="%_")["tasks"] == []
    service.store.update_task("older-title", title="字面量 %_ 任务")
    assert [task["tid"] for task in service.list_tasks(20, "p", search="%_")["tasks"]] == ["older-title"]
