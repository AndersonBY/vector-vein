from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from vv_agent.approval import ApprovalRequest
from vv_agent.config import ConfigError

from task_agent.client import TaskAgentError
from task_agent.host import DesktopTaskAgentHost
from task_agent.live_approval import LiveApprovalProvider
from task_agent.projection import project_event
from task_agent.runtime_settings import admit_change, apply_pending_change, permission_mode, public_settings, resolve_selection
from task_agent.service import TaskConflict
from task_agent.store import BusinessStore, now
from task_agent.usage import usage_summary


@pytest.fixture
def runtime_task(tmp_path, monkeypatch):
    settings = {"VERSION": "2", "endpoints": [{"id": "one", "api_base": "https://one.invalid/v1", "api_key": "synthetic-private-one"},
        {"id": "two", "api_base": "https://two.invalid/v1", "api_key": "synthetic-private-two"}], "backends": {"local": {"models": {
        "first": {"id": "same-wire", "endpoints": ["one"], "function_call_available": True, "context_length": 100000},
        "second": {"id": "same-wire", "endpoints": ["two"], "function_call_available": True, "context_length": 200000},
    }}}}
    monkeypatch.setattr("task_agent.runtime_settings.current_llm_settings", lambda: deepcopy(settings))
    store = BusinessStore(tmp_path / "tasks.db")
    from task_agent.config import build_model_snapshot
    snapshot = build_model_snapshot(settings, "Local", "first")
    snapshot.update(agent_profile={"agent_id": "general", "permission_mode": "full", "allow_shell": True}, skills=[], mcp_tools=[], project=None)
    store.create_task({"tid": "task_one", "thread_id": "task_one", "title": "Task", "goal": "Goal", "status": "PROCESSING", "current_turn_id": "turn_one", "model_provider": "Local", "model": "first", "reasoning_effort": "default", "config_snapshot": snapshot, "created_at": now(), "updated_at": now()})
    process = SimpleNamespace(calls=[], start=lambda: {"pid": 1})

    def request(method, params):
        process.calls.append((method, params))
        return {"threadId": params["threadId"], "inputId": params["inputId"], "accepted": True}

    process.request = request
    return store, process, settings


def change(**kwargs):
    return {"task_id": "task_one", "request_id": "request_one", "expected_revision": 0, **kwargs}


def test_permission_change_is_durable_idempotent_and_keeps_frozen_capabilities(runtime_task):
    store, process, _ = runtime_task
    original = deepcopy(store.get_task("task_one")["config_snapshot"])
    payload = change(permission_mode="ask")
    admit_change(store, payload)
    assert public_settings(store, store.get_task("task_one"))["pending_change_id"] == "request_one"
    with pytest.raises(TaskConflict):
        admit_change(store, change(request_id="different", permission_mode="full"))
    apply_pending_change(store, process, "task_one")
    assert permission_mode(store.get_task("task_one")) == "ask"
    assert not process.calls
    assert admit_change(store, payload)["receipt"] == {"accepted": True}
    assert public_settings(store, store.get_task("task_one"))["revision"] == 1
    assert {key: value for key, value in store.get_task("task_one")["config_snapshot"].items() if key != "runtime_settings"} == original
    with pytest.raises(TaskConflict):
        admit_change(store, change(request_id="stale", permission_mode="auto"))
    with pytest.raises(TaskConflict):
        admit_change(store, change(permission_mode="full"))


def test_model_change_pins_its_exact_endpoint_and_retries_the_same_native_identity(runtime_task):
    store, process, settings = runtime_task
    payload = change(model_provider="Local", model="second", reasoning_effort="default")
    admit_change(store, payload)
    real_request = process.request

    def lost_reply(method, params):
        real_request(method, params)
        raise TaskAgentError("Transport unavailable")

    process.request = lost_reply
    with pytest.raises(TaskAgentError):
        apply_pending_change(store, process, "task_one")
    assert public_settings(store, store.get_task("task_one"))["model"] == "first"
    assert public_settings(store, store.get_task("task_one"))["pending_change_id"] == "request_one"
    settings["backends"]["local"]["models"]["second"]["endpoints"] = ["one"]
    assert admit_change(store, payload)["receipt"] is None
    process.request = real_request
    apply_pending_change(store, process, "task_one")
    assert process.calls[0] == process.calls[1]
    assert process.calls[0][0] == "thread/model/select"
    selection = process.calls[0][1]["selection"]
    frozen = resolve_selection(store, selection)
    assert frozen["endpoint_options"][0]["endpoint_id"] == "two"
    assert "synthetic-private" not in repr(store.command("task_one", "request_one"))
    assert public_settings(store, store.get_task("task_one"))["model"] == "second"
    host = DesktopTaskAgentHost(store.path.parent, settings_loader=lambda: settings)
    client, resolved = host.resolve_model(selection)
    assert resolved.endpoint_options[0].endpoint.endpoint_id == "two"
    assert client.endpoint_targets[0].api_key == "synthetic-private-two"
    with pytest.raises(ValueError):
        host.resolve_model({**selection, "model": "forged-wire"})


def test_invalid_or_forged_settings_do_not_reserve_or_mutate(runtime_task):
    store, _, _ = runtime_task
    for values in ({"permission_mode": "invalid"}, {"permission_mode": "ask", "allow_shell": True}, {"model_provider": "missing", "model": "missing"}):
        with pytest.raises((ValueError, ConfigError)):
            admit_change(store, change(**values))
    assert public_settings(store, store.get_task("task_one"))["pending_change_id"] is None
    with pytest.raises(ValueError):
        resolve_selection(store, {"model": "same-wire", "route": {"desktop_task_id": "task_one", "desktop_change_id": "forged"}})


def test_live_approval_respects_user_changes_and_rechecks_an_inflight_risk_review(runtime_task):
    store, process, _ = runtime_task
    request = ApprovalRequest("approval_one", "bash", "call_one", arguments={"command": "echo safe"}, run_id="turn_one")
    provider = LiveApprovalProvider(store, "task_one")
    assert provider.should_request(request) is False
    admit_change(store, change(permission_mode="ask"))
    apply_pending_change(store, process, "task_one")
    assert provider.should_request(request) is True
    assert provider.decide(request) is None
    admit_change(store, change(request_id="auto_change", expected_revision=1, permission_mode="auto"))
    apply_pending_change(store, process, "task_one")
    provider.settings_loader = lambda: {"task_agent_approval": {"model_provider": "Local", "model": "reviewer"}}

    def evaluate(*_args):
        admit_change(store, change(request_id="back_to_ask", expected_revision=2, permission_mode="ask"))
        apply_pending_change(store, process, "task_one")
        return {"decision": "allow", "risk": "low", "reason": "read_only"}

    provider.evaluate = evaluate
    assert provider.decide(request) is None
    read = ApprovalRequest("read_one", "read_file", "read_one", arguments={"path": "outputs/result.md"})
    assert provider.should_request(read) is False
    external = ApprovalRequest("read_external", "read_file", "read_external", arguments={"path": str(store.path.parent.parent / "outside.txt")})
    assert provider.should_request(external) is True


def test_permission_change_preserves_an_already_presented_approval(runtime_task):
    store, process, _ = runtime_task
    store.save_state("task_one", {"pendingInteraction": {"kind": "approval", "requestId": "existing_approval"}})
    admit_change(store, change(permission_mode="full"))
    apply_pending_change(store, process, "task_one")
    provider = LiveApprovalProvider(store, "task_one")
    request = ApprovalRequest("existing_approval", "bash", "call", arguments={"command": "echo safe"})
    assert provider.should_request(request) is True
    assert provider.decide(request) is None
    assert provider.should_request(ApprovalRequest("subsequent_approval", "bash", "next_call")) is False


def test_token_usage_keeps_unknown_counts_unknown_and_deduplicates_provider_calls():
    event = {"type": "model_call_completed", "event_id": "e1", "run_id": "turn", "created_at": 1, "call_id": "call", "operation_id": "op", "operation": "agent_cycle",
        "usage": {"input_tokens": 100, "output_tokens": 10, "cache_usage": {"status": "provider_reported", "read_input_tokens": 60}, "provider_usage": {"private": "never-project"}}}
    projected = project_event(event)
    summary = usage_summary([projected, deepcopy(projected)])
    assert summary["input_tokens"] == 100 and summary["latest_input_tokens"] == 100
    assert summary["cache_read_tokens"] == 60 and summary["cache_input_tokens"] == 100
    assert "never-project" not in repr(projected)
    missing = project_event({**event, "event_id": "e2", "call_id": "call2", "usage": {"input_tokens": 50, "cache_usage": {"status": "accounting_missing"}}})
    summary = usage_summary([projected, missing])
    assert summary["input_tokens"] == 150 and summary["cache_input_tokens"] == 100 and summary["cache_missing_calls"] == 1
    assert usage_summary([])["input_tokens"] is None
    invalid = project_event({**event, "usage": {"input_tokens": True, "cache_usage": {"status": "provider_reported", "read_input_tokens": -1}}})
    assert usage_summary([invalid])["input_tokens"] is None


def test_open_skill_directory_uses_the_selected_retained_revision(tmp_path, monkeypatch):
    from task_agent.skills import SkillsLibrary
    library = SkillsLibrary(tmp_path)
    first = library.save({"skill_id": "example", "content": "---\nname: example\ndescription: Example skill.\n---\nFirst body."})
    first_path = Path(library.get_revision("example", first["version"])["bundle_path"])
    library.save({"skill_id": "example", "content": "---\nname: example\ndescription: Example skill.\n---\nSecond body."})
    opened = []
    monkeypatch.setattr("task_agent.skills.os.startfile", lambda path: opened.append(path), raising=False)
    monkeypatch.setattr("task_agent.skills.subprocess.Popen", lambda args: opened.append(Path(args[-1])))
    assert library.open_directory("example", version=1) == {"opened": True}
    assert opened == [first_path]
    library.delete("example")
    assert library.open_directory("example", version=1) == {"opened": True}
    with pytest.raises((ValueError, KeyError)):
        library.open_directory("../elsewhere")
