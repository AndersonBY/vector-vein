from copy import deepcopy

from vv_agent.model import ModelRef
from task_agent.config import DesktopModelProvider, build_model_snapshot


def test_named_model_keeps_frozen_backend_and_endpoint_order_when_ids_collide():
    settings = {"VERSION": "2", "endpoints": [{"id": "first", "api_key": "synthetic-one", "api_base": "https://first.invalid/v1"},
                              {"id": "second", "api_key": "synthetic-two", "api_base": "https://second.invalid/v1"}],
                "backends": {backend: {"models": {"friendly": {"id": "same-model", "endpoints": endpoints, "function_call_available": True}}}
                             for backend, endpoints in (("deepseek", ["first", "second"]), ("local", ["second"]))}}
    snapshot = build_model_snapshot(settings, "deepseek", "friendly")
    current = deepcopy(settings)
    current["backends"]["deepseek"]["models"]["friendly"]["endpoints"] = ["second"]
    current["endpoints"][0]["api_key"] = "rotated-synthetic"
    provider = DesktopModelProvider(lambda: current, snapshot=snapshot)
    for name in ("same-model", "friendly"):
        resolved = provider.resolve(ModelRef.named(name))
        assert resolved.backend == "deepseek"
        assert resolved.selected_model == "friendly"
        assert [option.endpoint.endpoint_id for option in resolved.endpoint_options] == ["first", "second"]
        assert resolved.endpoint_options[0].endpoint.api_key == "rotated-synthetic"
    assert "synthetic-one" not in repr(snapshot) and "rotated-synthetic" not in repr(snapshot)


def test_execution_failure_notices_are_scoped_and_do_not_store_exception_text(tmp_path):
    from task_agent.client import AppServerProcess
    process = AppServerProcess(tmp_path)
    process._observe({"method": "turn/completed", "params": {"threadId": "task1", "turnId": "task1/turn/one", "status": "failed", "error": "sensitive synthetic exception"}})
    assert process.execution_failed("task1", "task1/turn/one")
    assert not process.execution_failed("task2", "task2/turn/one")
    assert not process.execution_failed("task1", "task1/turn/two")
    assert "sensitive" not in repr(process._failures)
    process._observe({"method": "item/started", "params": {"threadId": "task1", "type": "modelCall"}})
    assert not process.execution_failed("task1", "task1/turn/one")


def test_internal_summary_keeps_its_frozen_endpoint_when_model_key_matches_wire_id():
    settings = {"VERSION": "2", "endpoints": [
        {"id": "first", "api_key": "synthetic-one", "api_base": "https://first.invalid/v1"},
        {"id": "second", "api_key": "synthetic-two", "api_base": "https://second.invalid/v1"}],
        "backends": {"local": {"models": {"friendly": {"id": "friendly", "endpoints": ["first"], "function_call_available": True}}}}}
    snapshot = build_model_snapshot(settings, "local", "friendly")
    settings["backends"]["local"]["models"]["friendly"]["endpoints"] = ["second"]
    provider = DesktopModelProvider(lambda: settings, snapshot=snapshot, summary_alias="desktop-summary/task_one")
    resolved = provider.resolve(ModelRef.backend("local", "desktop-summary/task_one"))
    assert resolved.model_id == "friendly"
    assert [option.endpoint.endpoint_id for option in resolved.endpoint_options] == ["first"]
