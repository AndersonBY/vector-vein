"""Adversarial selection and saved-authority checks for desktop integrations."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from task_agent.integrations import (
    validate_frozen_integrations,
    validate_mcp_tool_ids_format,
    validate_skill_ids_format,
)
from task_agent.mcp_library import MCPLibraryError
from task_agent.service import TaskAgentService
from task_agent.skills import SkillLibraryError


@pytest.mark.parametrize("invalid", [
    None, "one", ("one",), True, [1], ["one", "one"], ["../one"],
    [" one"], ["one\n"], ["x" * 129], [""],
])
def test_skill_selection_rejects_invalid_ids_before_lookup(invalid):
    with pytest.raises(SkillLibraryError, match="distinct skills"):
        validate_skill_ids_format(invalid)


@pytest.mark.parametrize("invalid", [
    None, "one", ("one",), True, [1], ["one", "one"], ["../one"],
    [" one"], ["one\n"], ["x" * 65], [""],
])
def test_mcp_selection_rejects_invalid_ids_before_lookup(invalid):
    with pytest.raises(MCPLibraryError, match="distinct MCP tools"):
        validate_mcp_tool_ids_format(invalid)


def test_selection_limits_and_explicit_empty_lists():
    assert validate_skill_ids_format([]) == []
    assert validate_mcp_tool_ids_format([]) == []
    assert len(validate_skill_ids_format([f"skill_{i}" for i in range(20)])) == 20
    assert len(validate_mcp_tool_ids_format([f"mcp_tool_{i}" for i in range(64)])) == 64
    with pytest.raises(SkillLibraryError):
        validate_skill_ids_format([f"skill_{i}" for i in range(21)])
    with pytest.raises(MCPLibraryError):
        validate_mcp_tool_ids_format([f"mcp_tool_{i}" for i in range(65)])


def test_explicit_null_task_override_is_rejected_before_task_creation(tmp_path):
    service = TaskAgentService(tmp_path, process=SimpleNamespace(stop=lambda: None), data_path=tmp_path)
    try:
        with pytest.raises(MCPLibraryError):
            service.create_task({"input_id": "null_override", "goal": "Validate selection", "mcp_tool_ids": None})
        assert service.store.get_task("null_override") is None
    finally:
        service.stop()


@pytest.mark.parametrize("key,value", [
    ("permission_mode", "full"), ("allow_shell", True), ("allow_file_writes", True),
    ("allow_sub_agents", True),
])
def test_frozen_integration_authority_also_preserves_saved_permissions(tmp_path, key, value):
    saved = {"skills": [], "mcp_tools": [], "agent_profile": {
        "permission_mode": "ask", "allow_shell": False,
        "allow_file_writes": False, "allow_sub_agents": False,
    }}
    forged = deepcopy(saved)
    forged["agent_profile"][key] = value
    with pytest.raises(ValueError, match="saved task"):
        validate_frozen_integrations(tmp_path, forged, saved)


@pytest.mark.parametrize("key,value", [
    ("permission_mode", "full"), ("allow_shell", True), ("allow_file_writes", True),
    ("allow_sub_agents", True),
])
def test_saved_legacy_profile_cannot_gain_new_permissions(tmp_path, key, value):
    saved = {"agent_profile": {}}
    forged = {"agent_profile": {key: value}}
    with pytest.raises(ValueError, match="saved task"):
        validate_frozen_integrations(tmp_path, forged, saved)
