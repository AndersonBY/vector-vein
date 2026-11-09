from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from task_agent.service import TaskAgentService, TaskConflict
from task_agent.scheduler import AgentScheduler, ScheduleError
from task_agent.store import BusinessStore, SCHEMA_VERSION


class Process:
    def __init__(self):
        self.calls = []
        self.threads = {}
        self.complete = True

    def start(self):
        return {"pid": 1, "connected": True}

    def stop(self):
        pass

    def request(self, method, params):
        self.calls.append((method, deepcopy(params)))
        if method == "thread/start":
            self.threads.setdefault(params["inputId"], [])
            return {"threadId": params["inputId"]}
        if method in {"turn/start", "turn/followUp"}:
            turn_id = f"{params['threadId']}/turn/{params['inputId']}"
            turns = self.threads[params["threadId"]]
            if not any(turn["turnId"] == turn_id for turn in turns):
                turns.append({"turnId": turn_id, "status": "completed" if self.complete else "running", "result": {"finalOutput": "Synthetic result"}})
            return {"turnId": turn_id}
        if method in {"thread/read", "thread/resume"}:
            return {"state": {"status": "idle"}, "turns": deepcopy(self.threads[params["threadId"]])}
        if method == "thread/events/list":
            return {"events": [], "more": False, "nextCursor": None}
        if method == "thread/model/select":
            return {"accepted": True, "inputId": params["inputId"], "threadId": params["threadId"]}
        raise AssertionError(method)


@pytest.fixture
def service(tmp_path, monkeypatch):
    settings = {"VERSION": "2", "endpoints": [{"id": "fixture", "api_base": "http://127.0.0.1:1/v1", "api_key": "synthetic-test"}],
                "backends": {"local": {"models": {"fixture": {"id": "fixture", "endpoints": ["fixture"], "function_call_available": True,
                    "capabilities": {"reasoning_efforts": ["low", "high"]}}}}}}
    for module in ("task_agent.service", "task_agent.scheduler", "task_agent.runtime_settings"):
        monkeypatch.setattr(module + ".current_llm_settings", lambda: deepcopy(settings))
    monkeypatch.setattr("task_agent.scheduler.now", lambda: "2026-11-06T00:00:00+00:00")
    result = TaskAgentService(tmp_path, process=Process(), data_path=tmp_path / "data")
    monkeypatch.setattr(result, "_start_watching", lambda: None)
    notices = []
    monkeypatch.setattr("utilities.desktop_notifications.notify_task_finished", notices.append)
    result.test_notices = notices
    yield result
    result.stop()


def payload(**changes):
    return {"schedule_id": "daily", "goal": "Synthetic scheduled goal", "model_provider": "Local", "model": "fixture",
            "reasoning_effort": "high", "cron_expression": "0 9 * * *", "timezone": "Asia/Shanghai", **changes}


def run(service, input_id="one"):
    admitted = service.scheduler.run_now({"schedule_id": "daily", "input_id": input_id})
    service.scheduler.tick(datetime(2026, 11, 6, tzinfo=timezone.utc))
    return service.store.get_task(admitted["task_id"])


def test_new_tasks_use_saved_model_project_roots_and_deduplicate_occurrences(service, tmp_path):
    roots = [tmp_path / "frontend", tmp_path / "backend"]
    for root in roots:
        root.mkdir()
    service.save_project({"project_id": "project", "roots": [str(root) for root in roots]})
    record = service.scheduler.save(payload(project_id="project", permission_mode="ask"))
    assert record["name"] == "Synthetic scheduled goal"
    assert record["next_run_at"] == "2026-11-06T01:00:00+00:00"
    first = run(service)
    assert first["project_id"] == "project"
    assert first["reasoning_effort"] == "high"
    assert first["config_snapshot"]["agent_profile"]["permission_mode"] == "ask"
    assert first["config_snapshot"]["project"]["roots"] == [str(root.resolve()) for root in roots]
    assert service._task_workspace(first["tid"]) == roots[0].resolve()
    assert run(service)["tid"] == first["tid"]
    second = run(service, "two")
    assert second["tid"] != first["tid"]
    assert len([call for call in service.process.calls if call[0] == "turn/start"]) == 2
    assert "synthetic-test" not in json.dumps(service.scheduler.list())


def test_continue_keeps_one_thread_applies_selection_each_turn_and_hides_restores(service):
    service.scheduler.save(payload(run_mode="continue", hide_after_run=True, notify_after_run=False))
    first = run(service)
    assert first["hidden"] == 1
    assert service.list_tasks()["tasks"] == []
    assert service.list_tasks(visibility="hidden")["tasks"][0]["tid"] == first["tid"]
    assert service.test_notices == []
    service.set_hidden({"task_id": first["tid"], "hidden": False, "expected_updated_at": first["updated_at"]})
    assert len(service.list_tasks()["tasks"]) == 1
    service.process.complete = False
    second = run(service, "two")
    assert second["tid"] == first["tid"] and second["hidden"] == 0
    assert len([call for call in service.process.calls if call[0] == "thread/start"]) == 1
    assert len([call for call in service.process.calls if call[0] == "turn/followUp"]) == 1
    assert [call for call in service.process.calls if call[0] == "thread/model/select"][-1][1]["selection"]["model_settings"]["reasoning"]["effort"] == "high"
    with pytest.raises(ScheduleError, match="busy"):
        run(service, "three")
    service.process.threads[first["tid"]][-1]["status"] = "completed"
    service.get_task(first["tid"])
    assert service.store.get_task(first["tid"])["hidden"] == 1


def test_schedule_can_bind_an_existing_hidden_task_and_continue_its_history(service):
    original = service.create_task({"input_id": "already_exists", "goal": "Original conversation", "model_provider": "Local", "model": "fixture"})["task"]
    service.store.update_task(original["tid"], hidden=1)
    saved = service.scheduler.save(payload(run_mode="continue", existing_task_id=original["tid"], goal="Scheduled follow-up"))
    assert saved["task_id"] == original["tid"]
    result = run(service)
    assert result["tid"] == original["tid"] and result["hidden"] == 0
    assert len(service.store.list_messages(result["tid"])) == 4
    assert len([call for call in service.process.calls if call[0] == "thread/start"]) == 1
    assert [call for call in service.process.calls if call[0] == "turn/followUp"][-1][1]["input"][0]["text"] == "Scheduled follow-up"
    with pytest.raises(ScheduleError, match="changed"):
        service.scheduler.save(payload(schedule_id="wrong_project", run_mode="continue", existing_task_id=original["tid"], project_id="another"))
    with pytest.raises(ScheduleError, match="task_missing"):
        service.scheduler.save(payload(schedule_id="missing", run_mode="continue", existing_task_id="missing"))
    with pytest.raises(ValueError):
        service.scheduler.save(payload(schedule_id="wrong_mode", existing_task_id=original["tid"]))


def test_completion_effects_are_once_per_turn_and_notify_switch_applies(service):
    service.scheduler.save(payload(hide_after_run=True))
    task = run(service)
    assert service.test_notices == ["COMPLETED"]
    for _ in range(3):
        service.get_task(task["tid"])
        service.scheduler.complete_task(task["tid"], task["current_turn_id"], "COMPLETED")
    assert service.test_notices == ["COMPLETED"]
    assert service.scheduler.get("daily")["last_run"]["status"] == "COMPLETED"
    with pytest.raises(TaskConflict):
        service.set_hidden({"task_id": task["tid"], "hidden": False, "expected_updated_at": "old"})
    with pytest.raises(ValueError):
        service.list_tasks(visibility="invalid")


def test_calendar_rule_timezone_due_slot_restart_and_missed_times(service):
    rule = {"unit": "week", "interval": 2, "anchor_date": "2026-11-06"}
    service.scheduler.save(payload(cron_expression="30 9 * * 1", recurrence=rule))
    assert service.scheduler.get("daily")["next_run_at"] == "2026-11-16T01:30:00+00:00"
    instant = datetime(2026, 11, 16, 1, 30, tzinfo=timezone.utc)
    service.scheduler.tick(instant)
    assert service.scheduler.get("daily")["next_run_at"] == "2026-11-30T01:30:00+00:00"
    service._scheduler = AgentScheduler(service)
    service.scheduler.tick(instant)
    assert len([call for call in service.process.calls if call[0] == "turn/start"]) == 1
    service.scheduler.tick(datetime(2026, 11, 30, 1, 40, tzinfo=timezone.utc))
    assert service.scheduler.get("daily")["last_run"]["error_code"] == "missed"
    assert len([call for call in service.process.calls if call[0] == "turn/start"]) == 1


def test_admitted_work_survives_controller_restart_without_duplicate_turn(service):
    service.scheduler.save(payload())
    admitted = service.scheduler.run_now({"schedule_id": "daily", "input_id": "durable"})
    service._scheduler = AgentScheduler(service)
    service.scheduler.tick(datetime(2026, 11, 6, tzinfo=timezone.utc))
    assert service.store.get_task(admitted["task_id"])["status"] == "COMPLETED"
    service.scheduler.tick(datetime(2026, 11, 6, tzinfo=timezone.utc))
    assert len([call for call in service.process.calls if call[0] == "turn/start"]) == 1


def test_lost_dispatch_response_retains_same_native_identity_on_explicit_retry(service):
    from task_agent.client import TaskAgentError
    service.scheduler.save(payload())
    request = service.process.request
    failed = False

    def lost(method, params):
        nonlocal failed
        result = request(method, params)
        if method == "turn/start" and not failed:
            failed = True
            raise TaskAgentError("Lost synthetic reply")
        return result

    service.process.request = lost
    task = run(service)
    record = service.scheduler.get("daily")["last_run"]
    assert record["status"] == "UNKNOWN"
    retry = {"schedule_id": "daily", "run_id": record["run_id"]}
    assert service.scheduler.retry_run(retry)["status"] == "ADMITTED"
    service._scheduler = AgentScheduler(service)
    service.scheduler.tick(datetime(2026, 11, 6, tzinfo=timezone.utc))
    assert service.scheduler.get("daily")["last_run"]["status"] == "COMPLETED"
    assert len(service.process.threads[task["tid"]]) == 1
    assert service.scheduler.retry_run(retry)["status"] == "COMPLETED"


@pytest.mark.parametrize("patch", [{"timezone": "Invalid/Zone"}, {"run_mode": "invalid"}, {"hide_after_run": "false"},
    {"recurrence": {"unit": "week", "interval": 0, "anchor_date": "2026-11-06"}}, {"cron_expression": "invalid"}, {"name": 123}])
def test_invalid_save_creates_no_schedule(service, patch):
    with pytest.raises((ValueError, KeyError)):
        service.scheduler.save(payload(**patch))
    assert service.scheduler.list() == []


def test_stale_edit_delete_and_disabled_manual_run(service):
    saved = service.scheduler.save(payload(enabled=False))
    assert saved["next_run_at"] is None
    with pytest.raises(ScheduleError, match="disabled"):
        run(service)
    with pytest.raises(ScheduleError, match="changed"):
        service.scheduler.save(payload(expected_updated_at="stale"))
    with pytest.raises(ScheduleError, match="changed"):
        service.scheduler.delete({"schedule_id": "daily", "expected_updated_at": "stale"})
    service.scheduler.delete({"schedule_id": "daily", "expected_updated_at": saved["updated_at"]})
    assert service.scheduler.list() == []


def test_api_validates_schedule_and_visibility_requests(service, monkeypatch):
    from api import task_agent_api
    monkeypatch.setattr(task_agent_api, "task_agent_service", lambda: service)
    api = task_agent_api.TaskAgentAPI()
    assert api.save_schedule(payload())["status"] == 200
    assert api.save_schedule(payload(timezone="Invalid/Zone"))["status"] == 400
    assert api.save_schedule(payload(expected_updated_at="stale"))["data"]["schedule_error"]["code"] == "changed"
    assert api.list({"visibility": "bad"})["status"] == 400
    admitted = api.run_schedule({"schedule_id": "daily", "input_id": "same"})
    assert admitted["status"] == 200
    assert api.run_schedule({"schedule_id": "daily", "input_id": "same"})["data"] == admitted["data"]
    assert api.schedules({})["data"]["schedules"][0]["last_run"]["task_id"] is None


def test_invalid_model_can_be_disabled_and_deleting_schedule_keeps_task_files(service, tmp_path):
    saved = service.scheduler.save(payload())
    task = run(service)
    file = service._task_workspace(task["tid"]) / "keep.txt"
    file.write_text("Local file", encoding="utf-8")
    disabled = service.scheduler.save(payload(expected_updated_at=saved["updated_at"], model="no-longer-configured", enabled=False))
    assert disabled["next_run_at"] is None
    service.scheduler.delete({"schedule_id": "daily", "expected_updated_at": disabled["updated_at"]})
    assert service.store.get_task(task["tid"]) is not None
    assert file.read_text(encoding="utf-8") == "Local file"


def test_v9_migration_retains_history_and_defaults_to_visible(tmp_path):
    store = BusinessStore(tmp_path / "tasks.db")
    with store.connect() as db:
        db.execute("DROP TABLE task_schedules")
        db.execute("DROP TABLE task_schedule_runs")
        db.execute("DROP TABLE task_completion_effects")
        db.execute("ALTER TABLE tasks DROP COLUMN hidden")
        db.execute("INSERT INTO tasks VALUES('old','old','Title','Goal','COMPLETED',NULL,'Local','fixture','default','{}','t','t',NULL)")
        db.execute("PRAGMA user_version=9")
    upgraded = BusinessStore(store.path)
    assert upgraded.get_task("old")["hidden"] == 0
    with upgraded.connect() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 10
