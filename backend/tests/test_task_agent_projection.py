import json
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from task_agent.client import TaskAgentError
from task_agent.files import list_files, preview_file, workspace_file
from task_agent.service import TaskAgentService, TaskConflict
from task_agent.store import BusinessStore, now


class Process:
    def __init__(self):
        self.calls = []
        self.fail = False
        self.terminal = False

    def start(self):
        return {"connected": True, "pid": 1}

    def request(self, method, params):
        self.calls.append((method, params))
        if self.fail:
            raise TaskAgentError("timeout")
        if method == "thread/events/list":
            return {"events": [], "nextCursor": {"seq": 1}, "throughCursor": {"seq": 1}, "more": False}
        if method in {"turn/steer", "turn/followUp"}:
            return {"turnId": "task/turn/start", "accepted": True}
        if method == "turn/action":
            return {"accepted": True}
        return {"state": {"status": "terminal" if self.terminal else "running"}, "turns": [{"turnId": "task/turn/start", "status": "failed" if self.terminal else "running", "result": {}}]}

    def stop(self):
        pass


def seed(service):
    timestamp = now()
    service.store.create_task({
        "tid": "task", "thread_id": "task", "title": "Goal", "goal": "Goal", "status": "PROCESSING",
        "current_turn_id": "task/turn/start", "model_provider": "Local", "model": "mock", "reasoning_effort": "default",
        "config_snapshot": {}, "created_at": timestamp, "updated_at": timestamp,
    })


def test_durable_terminal_state_wins_and_reads_do_not_change_recency(tmp_path):
    process = Process()
    service = TaskAgentService(tmp_path, process=process, data_path=tmp_path)
    seed(service)
    timestamp = service.store.get_task("task")["updated_at"]
    assert service.get_task("task")["task"]["updated_at"] == timestamp
    process.terminal = True
    assert service.get_task("task")["task"]["status"] == "FAILED"


def test_cached_detail_does_not_wait_for_engine_sync_or_the_service_lock(tmp_path):
    process = Process()
    service = TaskAgentService(tmp_path, process=process, data_path=tmp_path)
    seed(service)
    assert service.get_task("task", cached=True)["task"]["status"] == "PROCESSING"
    process.terminal = True
    held, release = threading.Event(), threading.Event()
    def occupy_sync_lock():
        with service._lock:
            held.set()
            release.wait(10)
    thread = threading.Thread(target=occupy_sync_lock)
    thread.start()
    try:
        assert held.wait(1)
        with ThreadPoolExecutor(max_workers=1) as executor:
            detail = executor.submit(service.get_task, "task", cached=True).result(timeout=1)
        assert detail["task"]["status"] == "PROCESSING"
        assert process.calls == []
    finally:
        release.set()
        thread.join(2)
    assert service.get_task("task")["task"]["status"] == "FAILED"
    with pytest.raises(KeyError):
        service.get_task("missing", cached=True)


def test_detail_and_sidebar_api_validate_read_options(monkeypatch):
    from api import task_agent_api
    calls = []
    service = SimpleNamespace(
        get_task=lambda tid, **options: calls.append((tid, options)) or {"task": {"tid": tid}},
        list_tasks=lambda *args: calls.append(args) or {"tasks": []},
    )
    monkeypatch.setattr(task_agent_api, "task_agent_service", lambda: service)
    api = task_agent_api.TaskAgentAPI()
    assert api.get({"task_id": "task", "cached": True})["status"] == 200
    assert calls[-1] == ("task", {"cached": True})
    assert api.get({"task_id": "task"})["status"] == 200
    assert calls[-1] == ("task", {"cached": False})
    assert api.get({"task_id": "task", "cached": "true"})["status"] == 400
    assert api.list({"project_id": "project", "limit": 5, "offset": 10})["status"] == 200
    assert calls[-1] == (5, "project", 10, "")
    assert api.list({"project_id": "project", "search": "report"})["status"] == 200
    assert calls[-1] == (20, "project", 0, "report")
    count = len(calls)
    for options in ({"offset": -1}, {"offset": True}, {"limit": 101}, {"search": []}, {"search": "x" * 257}):
        assert api.list(options)["status"] == 400
    assert len(calls) == count


def test_failed_submission_retries_identical_input_without_phantom_message(tmp_path):
    process = Process()
    service = TaskAgentService(tmp_path, process=process, data_path=tmp_path)
    seed(service)
    params = {"threadId": "task", "inputId": "steer", "expectedTurnId": "task/turn/start", "input": [{"type": "text", "text": "more"}]}
    process.fail = True
    with pytest.raises(TaskAgentError):
        service._execute("task", "steer", "turn/steer", params)
    assert service.store.list_messages("task") == []
    process.fail = False
    try:
        detail = service.send_message({"task_id": "task", "input_id": "steer", "text": "more"})
        assert detail["task"]["current_turn_id"] == "task/turn/start"
        service.send_message({"task_id": "task", "input_id": "steer", "text": "more"})
        calls = [p for method, p in process.calls if method == "turn/steer"]
        assert calls == [params, params]
        assert len(service.store.list_messages("task")) == 1
        with pytest.raises(TaskConflict):
            service.send_message({"task_id": "task", "input_id": "steer", "text": "different"})
    finally:
        service.stop()


def test_event_page_and_cursor_commit_together_and_deduplicate(tmp_path):
    service = TaskAgentService(tmp_path, process=Process(), data_path=tmp_path)
    seed(service)
    cursor = {"threadId": "task", "seq": 8, "offset": 1, "recordDigest": "d"}
    event = {"event_id": "event", "type": "tool_call_planned", "run_id": "task/turn/start", "created_at": 100,
             "tool_name": "read_file", "tool_call_id": "read", "arguments": {"path": "inputs/file.txt"}, "metadata": {"private": "DO_NOT_STORE"}}
    page = {"events": [{"cursor": cursor, "event": event}], "nextCursor": cursor}
    service.store.save_event_page("task", page)
    service.store.save_event_page("task", page)
    assert len(service.store.events("task")) == 1
    assert "DO_NOT_STORE" not in json.dumps(service.store.events("task"))
    bad = {"events": [page["events"][0], {"cursor": cursor, "event": {}}], "nextCursor": {"seq": 9}}
    with pytest.raises(KeyError):
        service.store.save_event_page("task", bad)
    assert service.store.projection("task")["cursor"] == cursor


def test_v1_upgrade_preserves_task_history(tmp_path):
    service = TaskAgentService(tmp_path, process=Process(), data_path=tmp_path)
    seed(service)
    service.store.upsert_message({"task_id": "task", "turn_id": "task/turn/start", "role": "user", "content": "Original", "status": "COMPLETED"})
    with service.store.connect() as connection:
        connection.execute("DROP INDEX tasks_project_order")
        connection.execute("ALTER TABLE tasks DROP COLUMN project_id")
        connection.execute("DROP TABLE task_projects")
        connection.execute("ALTER TABLE tasks DROP COLUMN hidden")
        for table in ("task_schedules", "task_schedule_runs", "task_completion_effects"):
            connection.execute(f"DROP TABLE {table}")
        for table in ("task_risk_reviews", "task_model_failures", "task_workflow_jobs", "task_projection", "task_events", "task_commands", "task_agent_profiles"):
            connection.execute(f"DROP TABLE {table}")
        connection.execute("PRAGMA user_version=1")
    upgraded = BusinessStore(service.store.path)
    assert upgraded.list_messages("task")[0]["content"] == "Original"
    assert upgraded.get_task("task")["title"] == "Goal"


def test_workspace_previews_are_bounded_and_cannot_escape(tmp_path):
    service = TaskAgentService(tmp_path, process=Process(), data_path=tmp_path)
    seed(service)
    root = service._task_workspace("task")
    (root / "outputs").mkdir(parents=True)
    (root / "outputs" / "report.md").write_text("x" * 150000, encoding="utf-8")
    outside = tmp_path / "private.txt"
    outside.write_text("secret", encoding="utf-8")
    for path in ("../../private.txt", str(outside), ".vv-agent/resources/file", "outputs/report.md:ads"):
        with pytest.raises(ValueError):
            workspace_file(service, "task", path)
    preview = preview_file(service, "task", "outputs/report.md")
    assert preview["truncated"] and len(preview["text"]) == 131072
    assert list_files(service, "task")["files"][0]["path"] == "outputs/report.md"


def test_disconnect_preserves_last_known_business_history(tmp_path):
    process = Process()
    service = TaskAgentService(tmp_path, process=process, data_path=tmp_path)
    seed(service)
    service.store.upsert_message({"task_id": "task", "turn_id": "task/turn/start", "role": "user", "content": "Goal", "status": "COMPLETED"})
    process.fail = True
    detail = service.get_task("task")
    assert detail["sync_error"] is True
    assert detail["messages"][0]["content"] == "Goal"
    assert detail["task"]["status"] == "PROCESSING"


def test_task_creation_rolls_back_without_its_initial_message(tmp_path):
    service = TaskAgentService(tmp_path, process=Process(), data_path=tmp_path)
    seed(service)
    task = {**service.store.get_task("task"), "tid": "incomplete", "thread_id": "incomplete"}
    with pytest.raises(KeyError):
        service.store.create_task(task, first_message={"task_id": "incomplete"})
    assert service.store.get_task("incomplete") is None


def test_watcher_keeps_old_active_tasks_and_unfinished_terminal_replay(tmp_path):
    service = TaskAgentService(tmp_path, process=Process(), data_path=tmp_path)
    seed(service)
    original = service.store.get_task("task")
    for index in range(101):
        tid = f"done{index}"
        service.store.create_task({**original, "tid": tid, "thread_id": tid, "status": "COMPLETED", "updated_at": now()})
    assert "task" not in {task["tid"] for task in service.store.list_tasks(100)}
    service.store.save_state("done0", {"history_pending": True})
    assert {task["tid"] for task in service.store.watched_tasks()} == {"task", "done0"}


def test_stopped_service_reads_history_without_restarting_child(tmp_path):
    process = Process()
    service = TaskAgentService(tmp_path, process=process, data_path=tmp_path)
    seed(service)
    service.get_task("task")
    calls = len(process.calls)
    service.stop()
    assert service.get_task("task")["sync_error"] is True
    assert len(process.calls) == calls


def test_command_timeline_uses_latest_handle_observation_without_rewriting_receipts():
    from task_agent.projection import build_timeline
    def event(identifier, turn, tool, status):
        return {"id": identifier, "turn_id": turn, "tool_call_id": identifier, "kind": "tool_call_completed", "tool_name": tool,
                "status": "success", "result": {"preview": json.dumps({"session_id": "command-one", "status": status})}}
    events = [event("start", "turn-one", "bash", "running"), event("check", "turn-one", "check_background_command", "unknown"),
              event("other", "turn-two", "bash", "running")]
    timeline, _ = build_timeline(events)
    assert [e["command_status"] for e in timeline] == ["unknown", "unknown", "running"]
    assert json.loads(timeline[0]["result"]["preview"])["status"] == "running"


def test_final_response_is_identified_without_duplicating_diagnostic_reply():
    from task_agent.projection import build_timeline
    events = [
        {"id": "progress", "kind": "assistant", "turn_id": "one", "text": "Working"},
        {"id": "answer", "kind": "assistant", "turn_id": "one", "text": "Done"},
        {"id": "completion", "kind": "final", "turn_id": "one", "text": "Done"},
        {"id": "next", "kind": "assistant", "turn_id": "two", "text": "Working again"},
    ]
    timeline, _ = build_timeline(events)
    assert [item["text"] for item in timeline] == ["Working", "Done", "Working again"]
    assert [item["final"] for item in timeline] == [False, True, False]
    assert "final" not in events[1]


@pytest.mark.parametrize("ending", ["final", "error", "run_cancelled"])
def test_ended_turn_does_not_present_an_unobserved_command_as_still_running(ending):
    from task_agent.projection import build_timeline
    receipt = {"session_id": "bg_win_original", "status": "running", "output": "partial output"}
    events = [
        {"id": "start", "kind": "tool_call_completed", "turn_id": "one", "tool_call_id": "start",
         "tool_name": "bash", "status": "success", "result": {"preview": json.dumps(receipt)}},
        {"id": "bad-query", "kind": "tool_call_completed", "turn_id": "one", "tool_call_id": "bad-query",
         "tool_name": "check_background_command", "status": "error", "error_code": "background_session_missing",
         "arguments": {"session_id": "bg_original"}, "result": {"preview": "Command handle unavailable"}},
        {"id": "end", "kind": ending, "turn_id": "one", "text": "Done"},
    ]
    timeline, _ = build_timeline(events)
    command, query = timeline[:2]
    assert command["command_status"] == "unknown"
    assert command["command_status_reason"] == "turn_ended_without_terminal_observation"
    assert json.loads(command["result"]["preview"]) == receipt
    assert query["error_code"] == "background_session_missing"
    assert "command_status" not in query
    confirmed = {"session_id": "bg_win_original", "status": "completed", "exit_code": 0}
    events.insert(2, {"id": "check", "kind": "tool_call_completed", "turn_id": "one", "tool_call_id": "check",
                      "tool_name": "check_background_command", "status": "success", "result": {"preview": json.dumps(confirmed)}})
    resolved, _ = build_timeline(events)
    assert resolved[0]["command_status"] == "completed"
    assert "command_status_reason" not in resolved[0]
    assert json.loads(resolved[0]["result"]["preview"]) == receipt
