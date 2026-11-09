from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import sqlite3
import threading
import time

import pytest

from api import task_agent_api
from task_agent.client import TaskAgentError
from task_agent.service import TaskAgentService
from test_task_agent_schedules import Process


class BlockingProcess(Process):
    def __init__(self):
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()
        self.start_calls = 0
        self.failure = None
        self.fail_turn_once = False
        self.complete = False
        self.stopped = False

    def start(self):
        self.start_calls += 1
        self.entered.set()
        assert self.release.wait(10), "Test did not release AppServer startup"
        if self.failure:
            raise self.failure
        return super().start()

    def request(self, method, params):
        assert not self.stopped, "RPC dispatched after service stop"
        result = super().request(method, params)
        if method == "turn/start" and self.fail_turn_once:
            self.fail_turn_once = False
            raise TaskAgentError("synthetic lost turn receipt SECRET")
        return result

    def stop(self):
        self.stopped = True
        self.release.set()


def payload(tid="first", **changes):
    return {"input_id": tid, "goal": "Synthetic task", "model_provider": "Local", "model": "fixture", **changes}


@pytest.fixture
def service(tmp_path, monkeypatch):
    settings = {"VERSION": "2", "endpoints": [{"id": "fixture", "api_base": "http://127.0.0.1:1/v1", "api_key": "synthetic"}],
                "backends": {"local": {"models": {"fixture": {"id": "fixture", "endpoints": ["fixture"]}}}}}
    monkeypatch.setattr("task_agent.service.current_llm_settings", lambda: deepcopy(settings))
    result = TaskAgentService(tmp_path, process=BlockingProcess(), data_path=tmp_path / "state")
    monkeypatch.setattr(result, "_start_watching", lambda: None)
    monkeypatch.setattr(task_agent_api, "task_agent_service", lambda: result)
    yield result
    result.stop()


def finished(service, tid="first"):
    with service._admission_lock:
        event = service._pending_starts.get(tid)
    if event:
        assert event.wait(5)
    return service.get_task(tid, cached=True)


def test_api_returns_persisted_pending_detail_before_cold_start_and_other_reads_do_not_wait(service):
    api = task_agent_api.TaskAgentAPI()
    started = time.perf_counter()
    first = api.create(payload())
    elapsed = time.perf_counter() - started
    print(f"local admission with cold host imports: {elapsed:.3f}s")
    assert first["status"] == 200 and first["data"]["start_pending"]
    assert first["data"]["task"]["status"] == "PENDING"
    assert first["data"]["messages"][0]["status"] == "PENDING"
    assert service.store.get_task("first") and service.process.entered.wait(2)
    assert service.process.calls == []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for cached in [True, False]:
            detail = pool.submit(api.get, {"task_id": "first", "cached": cached}).result(timeout=1)
            assert detail["data"]["start_pending"] and not detail["data"]["sync_error"]
        second = pool.submit(api.create, payload("second")).result(timeout=1)
    assert second["status"] == 200 and second["data"]["start_pending"]
    assert service.store.get_task("second")["status"] == "PENDING"
    assert service.process.start_calls == 1
    service.process.release.set()
    assert finished(service)["task"]["status"] == "PROCESSING"
    assert not finished(service, "second")["start_pending"]
    assert [method for method, _ in service.process.calls] == ["thread/start", "turn/start"] * 2


def test_duplicate_create_and_retry_share_one_start_and_freeze_original_inputs(service, tmp_path, monkeypatch):
    api = task_agent_api.TaskAgentAPI()
    attachment = tmp_path / "note.txt"
    attachment.write_text("original", encoding="utf-8")
    request = payload(turn_input_id="original_turn", attachments=[str(attachment)], mcp_tool_ids=[])
    first = api.create(request)["data"]
    assert service.process.entered.wait(2)
    attachment.unlink()
    monkeypatch.setattr(service, "get_profile", lambda _: pytest.fail("Frozen profile should be reused"))
    with ThreadPoolExecutor(max_workers=3) as pool:
        replay = pool.submit(api.create, {**request, "turn_input_id": "other_turn"}).result(timeout=1)
        retry = pool.submit(api.retry_start, {"task_id": "first"}).result(timeout=1)
    assert replay["data"]["task"]["current_turn_id"] == first["task"]["current_turn_id"] == "first/turn/original_turn"
    assert replay["data"]["messages"] == first["messages"]
    assert retry["data"]["start_pending"]
    for changes in [{"goal": "different"}, {"agent_id": "other"}, {"mcp_tool_ids": None}, {"permission_mode": "ask"}]:
        assert api.create({**request, **changes})["status"] in {400, 409}
    without_override = {key: value for key, value in request.items() if key != "mcp_tool_ids"}
    assert api.create(without_override)["status"] == 409
    service.process.release.set()
    detail = finished(service)
    assert detail["task"]["current_turn_id"] == "first/turn/original_turn"
    assert len(service.process.threads["first"]) == 1
    calls = service.process.calls
    assert [method for method, _ in calls] == ["thread/start", "turn/start"]
    assert calls[1][1]["inputId"] == "original_turn"
    assert first["messages"][0]["attachments"][0]["path"] in calls[1][1]["input"][0]["text"]


@pytest.mark.parametrize("failure", [TimeoutError("SECRET"), OSError("SECRET")])
def test_failure_is_durable_safe_and_retry_reuses_turn(service, failure):
    api = task_agent_api.TaskAgentAPI()
    service.process.failure = failure
    first = api.create(payload())["data"]
    service.process.release.set()
    detail = finished(service)
    assert detail["task"]["status"] == "PENDING"
    assert detail["sync_error"] and not detail["start_pending"]
    assert set(detail["start_model_failure"]) == {"category", "http_status", "parameter", "response_rejected"}
    assert "SECRET" not in json.dumps(detail)
    assert service.store.projection("first")["state"]["start_model_failure"] == detail["start_model_failure"]
    calls = service.process.start_calls
    assert service.get_task("first")["sync_error"]
    assert service.process.start_calls == calls
    service.process.failure = None
    assert api.retry_start({"task_id": "first"})["data"]["start_pending"]
    retried = finished(service)
    assert retried["task"]["current_turn_id"] == first["task"]["current_turn_id"]
    assert retried["task"]["status"] == "PROCESSING"
    assert not retried["sync_error"] and retried["start_model_failure"] is None


def test_lost_turn_receipt_retries_same_command_without_second_turn(service):
    api = task_agent_api.TaskAgentAPI()
    service.process.fail_turn_once = True
    service.process.release.set()
    api.create(payload(turn_input_id="stable"))
    assert finished(service)["sync_error"]
    assert service.store.command("first", "create_thread")["receipt"] is not None
    assert service.store.command("first", "stable")["receipt"] is None
    api.retry_start({"task_id": "first"})
    assert finished(service)["task"]["status"] == "PROCESSING"
    assert [method for method, _ in service.process.calls].count("thread/start") == 1
    turns = [params for method, params in service.process.calls if method == "turn/start"]
    assert len(turns) == 2 and turns[0] == turns[1]
    assert len(service.process.threads["first"]) == 1


def test_controls_and_deletion_reject_starting_tasks_without_wait_or_mutation(service):
    api = task_agent_api.TaskAgentAPI()
    created = api.create(payload())["data"]
    assert service.process.entered.wait(2)
    actions = [
        (api.action, {"task_id": "first", "action_id": "cancel", "turn_id": created["task"]["current_turn_id"], "action": {"kind": "cancel"}}),
        (api.update_runtime_settings, {"task_id": "first", "request_id": "change", "expected_revision": 0, "permission_mode": "ask"}),
        (api.send_message, {"task_id": "first", "input_id": "more", "text": "more"}),
        (api.task_context, {"task_id": "first"}),
        (api.recover, {"task_id": "first"}),
        (api.delete_task, {"task_id": "first", "expected_updated_at": created["task"]["updated_at"]}),
    ]
    with ThreadPoolExecutor(max_workers=1) as pool:
        for call, request in actions:
            assert pool.submit(call, request).result(timeout=1)["status"] == 409
    assert service.store.command("first", "change") is None
    assert service.process.calls == []


def test_stop_cancels_queued_starts_and_does_not_dispatch_after_inflight_start(service):
    api = task_agent_api.TaskAgentAPI()
    api.create(payload())
    assert service.process.entered.wait(2)
    api.create(payload("queued"))
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(service.stop).result(timeout=3)
    for tid in ("first", "queued"):
        detail = service.get_task(tid, cached=True)
        assert detail["task"]["status"] == "PENDING" and detail["sync_error"]
        assert not detail["start_pending"]
        assert api.retry_start({"task_id": tid})["status"] == 503
    assert not service._start_worker.is_alive()
    assert service.process.calls == []
    assert api.create(payload("after_stop"))["status"] == 503
    assert service.store.get_task("after_stop") is None


def test_restart_keeps_pending_for_explicit_retry_and_does_not_restart_completed(service, monkeypatch):
    api = task_agent_api.TaskAgentAPI()
    api.create(payload())
    assert service.process.entered.wait(2)
    service.stop()
    restarted = TaskAgentService(service.workspace, process=BlockingProcess(), data_path=service.task_root.parent)
    monkeypatch.setattr(restarted, "_start_watching", lambda: None)
    try:
        detail = restarted.get_task("first")
        assert not detail["start_pending"] and detail["sync_error"]
        assert restarted.process.start_calls == 0
        restarted.process.release.set()
        restarted.retry_start("first", background=True)
        assert finished(restarted)["task"]["status"] == "PROCESSING"
        restarted.store.update_task("first", status="COMPLETED")
        previous = list(restarted.process.calls)
        assert restarted.create_task(payload(), background=True)["task"]["status"] == "COMPLETED"
        assert restarted.process.calls == previous
    finally:
        restarted.stop()


def test_sync_default_still_waits_and_replay_does_not_double_start(service):
    with ThreadPoolExecutor(max_workers=2) as pool:
        synchronous = pool.submit(service.create_task, payload())
        assert service.process.entered.wait(2)
        assert not synchronous.done()
        replay = pool.submit(task_agent_api.TaskAgentAPI().create, payload()).result(timeout=1)
        assert replay["data"]["start_pending"]
        service.process.release.set()
        assert synchronous.result(timeout=5)["task"]["status"] == "PROCESSING"
    assert [method for method, _ in service.process.calls].count("turn/start") == 1


def test_validation_and_database_failure_never_queue_a_task(service, monkeypatch):
    api = task_agent_api.TaskAgentAPI()
    assert api.create(payload(goal=""))["status"] == 400
    assert service.store.get_task("first") is None
    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("Synthetic write failure")
    monkeypatch.setattr(service.store, "create_task", fail)
    assert api.create(payload())["status"] == 503
    assert service.store.get_task("first") is None
    assert not service._pending_starts and service.process.start_calls == 0


def test_retry_racing_stop_cannot_dispatch_a_new_turn(service):
    api = task_agent_api.TaskAgentAPI()
    api.create(payload())
    assert service.process.entered.wait(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        retry = pool.submit(api.retry_start, {"task_id": "first"})
        stopped = pool.submit(service.stop)
        assert retry.result(timeout=3)["status"] in {200, 503}
        stopped.result(timeout=3)
    assert service.process.calls == []
    assert not service.get_task("first", cached=True)["start_pending"]


@pytest.mark.parametrize("method", ["task_context", "compact_context", "update_runtime_settings", "send_message", "action", "approval"])
@pytest.mark.parametrize("payload", [None, [], "invalid", {}, {"task_id": []}])
def test_control_payload_validation_precedes_startup_checks(service, method, payload):
    result = getattr(task_agent_api.TaskAgentAPI(), method)(payload)
    assert result["status"] == 400
    assert service.process.start_calls == 0


def test_child_started_after_stop_returns_is_closed_before_any_rpc(service):
    class LateStart(BlockingProcess):
        def __init__(self):
            super().__init__()
            self.child_alive = False
            self.stop_calls = 0

        def start(self):
            self.entered.set()
            assert self.release.wait(10)
            self.child_alive = True
            return {"connected": True, "pid": 123}

        def stop(self):
            self.stop_calls += 1
            self.child_alive = False

    late = service.process = LateStart()
    task_agent_api.TaskAgentAPI().create(payload())
    assert late.entered.wait(2)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(service.stop).result(timeout=3)
        assert late.stop_calls == 1 and not late.child_alive
        assert service._start_worker.is_alive()
    finally:
        late.release.set()
    detail = finished(service)
    service._start_worker.join(timeout=2)
    assert late.stop_calls == 2 and not late.child_alive
    assert not service._start_worker.is_alive()
    assert late.calls == []
    assert detail["task"]["status"] == "PENDING" and detail["sync_error"]
    assert not detail["start_pending"]
