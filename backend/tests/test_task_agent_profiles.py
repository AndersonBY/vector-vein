from copy import deepcopy

import pytest

from task_agent.config import ConfigError
from task_agent.service import TaskAgentService
from task_agent.store import BusinessStore


@pytest.fixture
def profiles(tmp_path, monkeypatch):
    service = TaskAgentService.__new__(TaskAgentService)
    service.task_root = tmp_path
    service.store = BusinessStore(tmp_path / "tasks.db")
    llm = {"VERSION": "2", "endpoints": [{"id": "configured", "api_base": "https://example.invalid/v1", "api_key": "synthetic-private-key"}],
           "backends": {"local": {"models": {"enabled": {"id": "wire-model", "endpoints": ["configured"], "enabled": True,
               "function_call_available": True, "capabilities": {"reasoning_efforts": ["low"]}},
               "disabled": {"id": "disabled", "endpoints": ["configured"], "enabled": False}}}}}
    monkeypatch.setattr("task_agent.service.current_llm_settings", lambda: deepcopy(llm))
    monkeypatch.setattr("task_agent.workflows.selected_workflows", lambda values: [])
    return service


def payload(**changes):
    return {"agent_id": "research", "name": "研究助手", "description": "研究与资料整理", "instructions": "核对资料后交付报告。",
            "max_cycles": 40, "allow_file_writes": True, "allow_shell": True, "allow_sub_agents": True, "permission_mode": "ask",
            "model_provider": "Local", "model": "enabled", "reasoning_effort": "low", **changes}


def test_profile_detail_preserves_model_defaults_timestamps_and_never_credentials(profiles, monkeypatch):
    first = profiles.save_profile(payload(api_key="must-not-be-stored"))
    assert profiles.get_profile("research") == first
    second = profiles.save_profile(payload(name="研究助手新版"))
    assert second["created_at"] == first["created_at"] and second["updated_at"] >= first["updated_at"]
    assert profiles.list_profiles()[1]["model"] == "enabled"
    assert "private-key" not in repr(profiles.list_profiles()) and "must-not-be-stored" not in repr(second)
    monkeypatch.setattr(profiles.store, "profiles", lambda: (_ for _ in ()).throw(AssertionError("must not scan the catalog")))
    assert profiles.get_profile("research")["name"] == "研究助手新版"
    with pytest.raises(KeyError):
        profiles.get_profile("missing")


@pytest.mark.parametrize("changes", [{"model": "missing"}, {"model": "disabled"}, {"model_provider": "missing"},
                                       {"reasoning_effort": "high"}, {"model_provider": "", "model": "", "reasoning_effort": "low"}])
def test_invalid_profile_model_does_not_overwrite_saved_configuration(profiles, changes):
    previous = profiles.save_profile(payload())
    with pytest.raises((ConfigError, ValueError)):
        profiles.save_profile(payload(**changes))
    assert profiles.get_profile("research") == previous


def test_profile_can_follow_workbench_and_builtin_configuration_is_editable(profiles):
    saved = profiles.save_profile(payload(model_provider="", model="", reasoning_effort="default"))
    assert saved["model"] == "" and saved["model_provider"] == ""
    assert profiles.get_profile("general")["agent_id"] == "general"
    changed = profiles.save_profile(payload(agent_id="general", instructions="", permission_mode="full"))
    assert profiles.get_profile("general") == changed
    assert [item["agent_id"] for item in profiles.list_profiles()].count("general") == 1
    assert profiles.list_profiles()[0]["permission_mode"] == "full"
    with pytest.raises(ValueError):
        profiles.save_profile(payload(instructions=""))


def test_single_profile_api_reports_missing_and_invalid_identifiers(profiles, monkeypatch):
    from api import task_agent_api
    monkeypatch.setattr(task_agent_api, "task_agent_service", lambda: profiles)
    api = task_agent_api.TaskAgentAPI()
    assert api.profile({"agent_id": "general"})["status"] == 200
    assert api.profile({"agent_id": "missing"})["status"] == 404
    assert api.profile({"agent_id": "../escape"})["status"] == 400


@pytest.mark.parametrize("limit", [0, 1, 1000, 2**32 - 1])
def test_profile_persists_disabled_and_explicit_cycle_limits(profiles, limit):
    saved = profiles.save_profile(payload(max_cycles=limit))
    assert saved["max_cycles"] == limit
    assert profiles.get_profile("research")["max_cycles"] == limit


@pytest.mark.parametrize("limit", [None, False, True, -1, 1.5, "50", 2**32])
def test_profile_rejects_invalid_cycle_limits_without_overwriting(profiles, limit):
    previous = profiles.save_profile(payload(max_cycles=0))
    with pytest.raises(ValueError, match="Invalid agent limits"):
        profiles.save_profile(payload(max_cycles=limit))
    assert profiles.get_profile("research") == previous


def test_new_and_builtin_profiles_default_to_no_configured_cycle_limit(profiles):
    request = payload()
    del request["max_cycles"]
    assert profiles.save_profile(request)["max_cycles"] == 0
    assert profiles.get_profile("general")["max_cycles"] == 0
