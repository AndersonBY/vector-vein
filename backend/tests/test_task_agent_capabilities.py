from types import SimpleNamespace

import pytest

from task_agent.config import build_model_snapshot
from task_agent.host import DesktopTaskAgentHost, SHELL_TOOLS, SUB_AGENT_TOOLS, command_shell
from task_agent.service import TaskAgentService


SETTINGS = {'VERSION': '2', 'endpoints': [{'id': 'test', 'api_base': 'http://localhost:1/v1', 'api_key': 'synthetic'}],
            'backends': {'local': {'models': {'test': {'id': 'test', 'endpoints': ['test'], 'function_call_available': True}}}}}


@pytest.mark.parametrize('shell,children', [(False, False), (True, False), (False, True), (True, True)])
def test_capabilities_and_frozen_model_settings(tmp_path, shell, children):
    snapshot = build_model_snapshot(SETTINGS, 'local', 'test')
    snapshot['reasoning_effort'] = 'low'
    snapshot['agent_profile'] = {'allow_shell': shell, 'allow_sub_agents': children, 'allow_file_writes': False}
    snapshot['command_shell'] = command_shell(snapshot['agent_profile'])
    request = SimpleNamespace(thread_id='task', cwd=str(tmp_path / 'workspaces/task'), metadata={'model_snapshot': snapshot})
    host = DesktopTaskAgentHost(tmp_path, settings_loader=lambda: SETTINGS)
    config = host.build_run_config(request)
    agent = host.resolve_agent(request)
    assert set(SHELL_TOOLS).issubset(config.tool_policy.allowed_tools) == shell
    assert set(SUB_AGENT_TOOLS).issubset(config.tool_policy.allowed_tools) == children
    assert bool(agent.sub_agents) == children
    assert not {'write_file', 'edit_file'}.intersection(config.tool_policy.allowed_tools)
    assert config.model_provider.default_settings(config.model).reasoning == {'effort': 'low'}
    if shell or children:
        assert 'bash' in config.tool_registry_factory().list_planner_extra_tool_names()
    if children:
        assert agent.sub_agents['worker'].model == config.model.model_id
        assert "agent_id='worker'" not in agent.sub_agents['worker'].system_prompt


def test_legacy_snapshot_keeps_original_tool_permissions(tmp_path):
    snapshot = build_model_snapshot(SETTINGS, 'local', 'test')
    snapshot['agent_profile'] = {'allow_file_writes': True}
    request = SimpleNamespace(thread_id='task', cwd=str(tmp_path / 'workspaces/task'), metadata={'model_snapshot': snapshot})
    host = DesktopTaskAgentHost(tmp_path, settings_loader=lambda: SETTINGS)
    config = host.build_run_config(request)
    assert not set(SHELL_TOOLS + SUB_AGENT_TOOLS).intersection(config.tool_policy.allowed_tools)
    assert config.tool_registry_factory is None
    assert not host.resolve_agent(request).sub_agents


@pytest.mark.parametrize("limit", [0, 1, 1000])
def test_cycle_budget_reaches_parent_and_child_without_sdk_default_fallback(tmp_path, limit):
    from vv_agent.run_config import effective_run_config
    from task_agent.config import MAX_CYCLE_LIMIT

    snapshot = build_model_snapshot(SETTINGS, "local", "test")
    snapshot["agent_profile"] = {"max_cycles": limit, "allow_sub_agents": True}
    request = SimpleNamespace(thread_id="task", cwd=str(tmp_path / "workspaces" / "task"), metadata={"model_snapshot": snapshot})
    host = DesktopTaskAgentHost(tmp_path, settings_loader=lambda: SETTINGS)
    agent, config = host.resolve_agent(request), host.build_run_config(request)
    expected = MAX_CYCLE_LIMIT if limit == 0 else limit
    assert config.max_cycles == expected
    assert effective_run_config(agent, config).max_cycles == expected
    assert agent.sub_agents["worker"].max_cycles == expected


@pytest.mark.parametrize('values', [{'allow_shell': 'true'}, {'allow_sub_agents': 1}, {'shell': 'cmd /c arbitrary'}, {'shell': []}])
def test_profile_validates_tool_settings(tmp_path, values):
    service = TaskAgentService(tmp_path, data_path=tmp_path)
    with pytest.raises(ValueError, match='Invalid agent tool settings'):
        service.save_profile({'agent_id': 'test', 'name': 'Test', 'instructions': 'Test', **values})


def test_background_command_ownership_and_stop(tmp_path):
    import json
    import time
    from dataclasses import replace
    from vv_agent.tools.base import ToolContext
    from task_agent.host import desktop_tool_registry
    registry = desktop_tool_registry()
    run_bash_command = registry.get_executor('bash').handler
    check_background_command = registry.get_executor('check_background_command').handler
    stop_background_command = registry.get_executor('stop_background_command').handler
    from vv_agent.workspace.local import LocalWorkspaceBackend

    shell = command_shell({"allow_shell": True})
    command = "sleep 15" if shell["kind"] == "bash" else "Start-Sleep -Seconds 15"
    context = ToolContext(workspace=tmp_path, workspace_backend=LocalWorkspaceBackend(tmp_path), shared_state={}, cycle_index=1,
                          task_id="owner", tool_call_id="command", task_metadata={"bash_shell": shell["executable"]})
    result = json.loads(run_bash_command(context, {"command": command, "yield_time_ms": 0, "timeout_seconds": 30}).content)
    handle = {"session_id": result["session_id"]}
    try:
        wrong_owner = check_background_command(replace(context, task_id="other"), handle)
        assert wrong_owner.error_code
        assert check_background_command(context, handle).error_code is None
        assert stop_background_command(replace(context, task_id="other"), handle).error_code
        stopped = stop_background_command(context, handle)
        # POSIX terminal receipts contain plain output; structured state lives in metadata.
        deadline = time.monotonic() + 5
        while stopped.metadata["status"] in {"stopping", "unknown"} and time.monotonic() < deadline:
            time.sleep(0.05)
            stopped = check_background_command(context, handle)
        assert stopped.metadata["status"] == "stopped", stopped
        assert stopped.metadata["session_id"] == handle["session_id"]
        assert stopped.metadata["exit_code"] is not None
        assert check_background_command(context, handle).metadata["status"] == "stopped"
    finally:
        stop_background_command(context, handle)
