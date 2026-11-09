"""Independent public-SDK and trust-boundary checks for task MCP execution."""
import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import pytest
from vv_agent.session.providers import Accepted, Definitive, validate_provider_handle, validate_provider_result
from vv_agent.session.records import Record, digest
from vv_agent.tools.base import ToolContext
from vv_agent.types import ToolExecutionResult, ToolResultStatus
from vv_agent.workspace.local import LocalWorkspaceBackend

from task_agent.integrations import selected_mcp_tools
from task_agent.mcp_library import MCPLibrary
from task_agent import mcp_runtime
from task_agent.store import now


@pytest.fixture
def managed_mcp(tmp_path):
    root, workspace = tmp_path / "task-agent", tmp_path / "workspace"
    workspace.mkdir()
    call_log = tmp_path / "calls.jsonl"
    library = MCPLibrary(root)
    library.save({
        "server_id": "review_server", "name": "Review MCP", "transport": "stdio",
        "command": sys.executable,
        "args": [str(Path(__file__).with_name("mcp_test_server.py").resolve()), "runtime_stateful"],
        "env": {"FIXTURE_CALL_LOG": str(call_log)}, "timeout_seconds": 5,
    })
    tested = library.test("review_server")
    descriptors = selected_mcp_tools(root, library.store, [tool["namespaced_name"] for tool in tested["tools"]])
    descriptor = next(tool for tool in descriptors if tool["name"] == "stateful_step")
    timestamp = now()
    library.store.create_task({
        "tid": "review_task", "thread_id": "review_task", "title": "MCP boundary review",
        "goal": "Use only the synthetic local MCP fixture", "status": "PROCESSING",
        "current_turn_id": "review_task/turn/one", "model_provider": "fixture", "model": "fixture",
        "reasoning_effort": "default", "config_snapshot": {"mcp_tools": deepcopy(descriptors)},
        "created_at": timestamp, "updated_at": timestamp,
    })
    runtime = mcp_runtime.MCPRuntimeManager(root)
    value = SimpleNamespace(root=root, workspace=workspace, library=library, runtime=runtime,
                            descriptor=descriptor, descriptors=descriptors, call_log=call_log)
    try:
        yield value
    finally:
        runtime.shutdown()


def invoke(fixture, arguments, *, descriptor=None):
    selected = descriptor or fixture.descriptor
    request = {"id": "review-call", "name": selected["namespaced_name"], "arguments": arguments}
    plan = Record(
        record_id="review-plan", kind="op_planned", session_id="review_task",
        turn_id="review_task/turn/one", operation_id="tool/1", attempt=1,
        payload={"op_kind": "tool", "purpose": None, "request": request, "request_digest": digest(request),
                 "context_version": "review", "dependencies": [], "tool": None, "idempotency_key": None,
                 "budget_admission": {}, "not_before_ms": None, "provider_binding": selected["namespaced_name"],
                 "consumed_unknowns": []},
    )
    context = ToolContext(workspace=fixture.workspace, shared_state={}, cycle_index=0,
                          workspace_backend=LocalWorkspaceBackend(fixture.workspace),
                          task_id=plan.turn_id, metadata={"session_id": plan.session_id})
    provider = mcp_runtime.MCPToolProvider(fixture.root, "review_task", fixture.workspace,
                                         selected, fixture.runtime, wait_window_seconds=0)
    outcome = provider.submit(plan, context=context)
    handle = outcome.handle if isinstance(outcome, Accepted) else None
    if handle:
        validate_provider_handle(plan, handle)
    deadline = time.monotonic() + 12
    while isinstance(outcome, Accepted) and time.monotonic() < deadline:
        time.sleep(0.05)
        outcome = provider.query(outcome.handle)
    assert isinstance(outcome, Definitive), outcome
    validate_provider_result(plan, outcome, handle)
    return ToolExecutionResult.from_dict(outcome.result)


def test_invalid_arguments_never_reach_the_actual_server(managed_mcp):
    result = invoke(managed_mcp, {"tag": 42})
    assert result.status_code == ToolResultStatus.ERROR
    assert result.error_code == "invalid_tool_arguments", result.to_dict()
    assert not managed_mcp.call_log.exists()
    assert all(job["result"] is not None for job in managed_mcp.library.store.mcp_jobs("review_task"))


def test_forged_schema_cannot_replace_the_saved_descriptor(managed_mcp):
    forged = deepcopy(managed_mcp.descriptor)
    forged["input_schema"] = {"type": "object"}
    result = invoke(managed_mcp, {"tag": "forged"}, descriptor=forged)
    assert result.status_code == ToolResultStatus.ERROR
    assert result.error_code == "mcp_descriptor_mismatch", result.to_dict()
    assert not managed_mcp.call_log.exists()


def test_missing_business_task_cannot_grant_mcp_access(managed_mcp):
    with managed_mcp.library.store.connect() as connection:
        connection.execute("DELETE FROM tasks WHERE tid='review_task'")
    result = invoke(managed_mcp, {"tag": "no-task"})
    assert result.status_code == ToolResultStatus.ERROR
    assert result.error_code == "mcp_task_missing", result.to_dict()
    assert not managed_mcp.call_log.exists()


def test_official_transport_enters_and_exits_in_the_same_owner_task(managed_mcp, monkeypatch):
    events = []
    original = mcp_runtime.open_mcp_client

    @asynccontextmanager
    async def observed(*args, **kwargs):
        events.append(("enter", asyncio.current_task()))
        try:
            async with original(*args, **kwargs) as client:
                yield client
        finally:
            events.append(("exit", asyncio.current_task()))

    monkeypatch.setattr(mcp_runtime, "open_mcp_client", observed)
    result = invoke(managed_mcp, {"tag": "owner"})
    managed_mcp.runtime.close_task("review_task")
    assert [event[0] for event in events] == ["enter", "exit"]
    assert events[0][1] is events[1][1]
    assert result.status_code == ToolResultStatus.SUCCESS, result.to_dict()


def test_failed_tool_diagnostic_survives_in_public_run_summary(managed_mcp):
    descriptor = next(tool for tool in managed_mcp.descriptors if tool["name"] == "media_and_error")
    result = invoke(managed_mcp, {"fail": True}, descriptor=descriptor)
    assert result.status_code == ToolResultStatus.ERROR
    assert result.error_code
    summary = mcp_runtime.mcp_run_views(managed_mcp.library.store, "review_task")[0]
    assert summary["status"] == "FAILED"
    assert summary["error_code"] == result.error_code
