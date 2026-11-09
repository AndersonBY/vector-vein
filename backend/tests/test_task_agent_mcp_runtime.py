from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from vv_agent.session.providers import (
    Accepted,
    Definitive,
    Unknown,
    validate_provider_handle,
    validate_provider_result,
)
from vv_agent.session.records import Record, digest as record_digest
from vv_agent.tools.base import ToolContext
from vv_agent.workspace.local import LocalWorkspaceBackend

from task_agent.integrations import selected_mcp_tools
from task_agent.mcp_library import MCPLibrary
from task_agent.mcp_runtime import MCPRuntimeManager, MCPToolProvider, mcp_run_views, mcp_tools
from task_agent.store import BusinessStore, now

FIXTURE_SCRIPT = str((Path(__file__).parent / "mcp_test_server.py").resolve())


def _is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        res = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in res.stdout
    try:
        import os

        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _seed_business_task(
    store: BusinessStore,
    task_id: str,
    mcp_tool_descriptors: list[dict[str, Any]],
) -> None:
    timestamp = now()
    store.create_task(
        {
            "tid": task_id,
            "thread_id": task_id,
            "title": f"Task {task_id}",
            "goal": "Test MCP runtime execution",
            "status": "PROCESSING",
            "current_turn_id": f"{task_id}/turn/1",
            "model_provider": "fixture",
            "model": "fixture",
            "reasoning_effort": "default",
            "config_snapshot": {"mcp_tools": deepcopy(mcp_tool_descriptors)},
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    )


def _setup_stateful_server(
    root: Path,
    *,
    server_id: str = "stateful-srv",
    secret: str = "SYNTHETIC-SECRET-ALPHA-123",
    timeout_seconds: float = 10.0,
    extra_env: dict[str, str] | None = None,
) -> tuple[MCPLibrary, dict[str, Any], list[dict[str, Any]]]:
    lib = MCPLibrary(root)
    env = {"SYNTHETIC_STDIO_SECRET": secret}
    if extra_env:
        env.update(extra_env)
    lib.save(
        {
            "server_id": server_id,
            "name": "Stateful Stdio Server",
            "transport": "stdio",
            "command": sys.executable,
            "args": [FIXTURE_SCRIPT, "runtime_stateful"],
            "env": env,
            "timeout_seconds": timeout_seconds,
            "enabled": True,
        }
    )
    discovered = lib.test(server_id)
    tool_ids = [t["namespaced_name"] for t in discovered["tools"]]
    frozen = selected_mcp_tools(root, lib.store, tool_ids)
    return lib, discovered, frozen


def _make_ctx_and_plan(
    workspace: Path,
    descriptor: dict[str, Any],
    arguments: Any,
    *,
    session_id: str = "sess_parent",
    turn_task_id: str = "turn_1",
    tool_call_id: str = "call_1",
    operation_id: str = "op_1",
    attempt: int = 1,
    request_digest: str = "",
) -> tuple[ToolContext, Record]:
    namespaced = descriptor["namespaced_name"]
    request = {"id": tool_call_id, "name": namespaced, "arguments": arguments}
    req_digest = request_digest or record_digest(request)
    plan = Record(
        record_id=f"rec-{session_id}-{operation_id}-{attempt}",
        kind="op_planned",
        session_id=session_id,
        turn_id=turn_task_id,
        operation_id=operation_id,
        attempt=attempt,
        payload={
            "op_kind": "tool",
            "purpose": None,
            "request": request,
            "request_digest": req_digest,
            "context_version": "1",
            "dependencies": [],
            "tool": None,
            "idempotency_key": None,
            "budget_admission": {},
            "not_before_ms": None,
            "provider_binding": namespaced,
            "consumed_unknowns": [],
        },
    )
    ctx = ToolContext(
        workspace=workspace,
        shared_state={},
        cycle_index=0,
        workspace_backend=LocalWorkspaceBackend(workspace),
        task_id=turn_task_id,
        metadata={"session_id": session_id},
    )
    return ctx, plan


def _drive_to_terminal(
    provider: MCPToolProvider,
    plan: Record,
    outcome: Any,
    *,
    timeout: float = 10.0,
) -> tuple[Any, dict[str, Any] | None]:
    deadline = time.time() + timeout
    cur = outcome
    first_handle: dict[str, Any] | None = None
    if isinstance(cur, Accepted):
        first_handle = cur.handle
        validate_provider_handle(plan, first_handle)
    while isinstance(cur, Accepted) and time.time() < deadline:
        time.sleep(0.05)
        cur = provider.query(cur.handle)
    if isinstance(cur, Definitive):
        validate_provider_result(plan, cur, first_handle)
    return cur, first_handle


def test_sequential_stateful_calls_share_pid_and_multiple_tools_share_connection(tmp_path: Path) -> None:
    root = tmp_path / "state"
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    pid_file = tmp_path / "server.pid"
    call_log = tmp_path / "calls.log"

    lib, _disc, frozen = _setup_stateful_server(
        root,
        extra_env={
            "FIXTURE_PID_FILE": str(pid_file),
            "FIXTURE_CALL_LOG": str(call_log),
        },
    )
    _seed_business_task(lib.store, "task_1", frozen)
    by_name = {d["name"]: d for d in frozen}
    step_desc = by_name["stateful_step"]
    peer_desc = by_name["peer_info"]

    # Verify FunctionTool builders always enforce needs_approval=True even when read_only_hint is True
    built_tools = mcp_tools(frozen)
    assert len(built_tools) == 3
    for ft in built_tools:
        assert ft.needs_approval is True

    # Test real default constructor (uses root / "tasks.db")
    runtime = MCPRuntimeManager(root)
    assert runtime._thread is None  # Offline init

    try:
        step_provider = MCPToolProvider(
            root,
            "task_1",
            ws,
            step_desc,
            runtime,
            wait_window_seconds=2.0,
        )
        peer_provider = MCPToolProvider(
            root,
            "task_1",
            ws,
            peer_desc,
            runtime,
            wait_window_seconds=2.0,
        )

        ctx1, plan1 = _make_ctx_and_plan(
            ws, step_desc, {"tag": "first"}, session_id="sess_main", operation_id="op_a", tool_call_id="tc_1"
        )
        out1, _ = _drive_to_terminal(step_provider, plan1, step_provider.submit(plan1, context=ctx1))
        assert isinstance(out1, Definitive)
        assert out1.result["status_code"] == "SUCCESS"
        payload1 = json.loads(out1.result["content"])
        assert payload1["untrusted_mcp_output"] is True
        assert "SYNTHETIC-SECRET-ALPHA-123" not in out1.result["content"]
        assert payload1["structured_content"]["call_count"] == 1
        pid1 = payload1["structured_content"]["pid"]

        ctx2, plan2 = _make_ctx_and_plan(
            ws, step_desc, {"tag": "second"}, session_id="sess_main", operation_id="op_b", tool_call_id="tc_2"
        )
        out2, _ = _drive_to_terminal(step_provider, plan2, step_provider.submit(plan2, context=ctx2))
        assert isinstance(out2, Definitive)
        payload2 = json.loads(out2.result["content"])
        assert payload2["structured_content"]["call_count"] == 2
        assert payload2["structured_content"]["pid"] == pid1

        # Second tool on the same server shares the exact same live process and state counter
        ctx3, plan3 = _make_ctx_and_plan(
            ws, peer_desc, {"note": "hello"}, session_id="sess_main", operation_id="op_c", tool_call_id="tc_3"
        )
        out3, _ = _drive_to_terminal(peer_provider, plan3, peer_provider.submit(plan3, context=ctx3))
        assert isinstance(out3, Definitive)
        payload3 = json.loads(out3.result["content"])
        assert payload3["structured_content"]["call_count"] == 3
        assert payload3["structured_content"]["pid"] == pid1

        # Explicit close_task terminates the owned server process
        assert _is_pid_running(pid1)
        runtime.close_task("task_1")
        deadline = time.time() + 5.0
        while _is_pid_running(pid1) and time.time() < deadline:
            time.sleep(0.1)
        assert not _is_pid_running(pid1)
    finally:
        runtime.shutdown()


def test_parallel_child_sessions_do_not_collide_and_repeated_submit_never_replays(tmp_path: Path) -> None:
    root = tmp_path / "state"
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    call_log = tmp_path / "calls.log"

    lib, _disc, frozen = _setup_stateful_server(
        root,
        extra_env={"FIXTURE_CALL_LOG": str(call_log)},
    )
    _seed_business_task(lib.store, "task_2", frozen)
    step_desc = next(d for d in frozen if d["name"] == "stateful_step")

    runtime = MCPRuntimeManager(root)
    try:
        provider = MCPToolProvider(
            root,
            "task_2",
            ws,
            step_desc,
            runtime,
            wait_window_seconds=2.0,
        )

        # Two distinct child session_ids with identical turn task_id, operation_id, attempt, and arguments
        ctx_child_a, plan_a = _make_ctx_and_plan(
            ws,
            step_desc,
            {"tag": "shared_arg"},
            session_id="child_session_alpha",
            turn_task_id="same_turn_id",
            operation_id="same_op_id",
            attempt=1,
            tool_call_id="tc_a",
        )
        ctx_child_b, plan_b = _make_ctx_and_plan(
            ws,
            step_desc,
            {"tag": "shared_arg"},
            session_id="child_session_beta",
            turn_task_id="same_turn_id",
            operation_id="same_op_id",
            attempt=1,
            tool_call_id="tc_b",
        )

        out_a, _ = _drive_to_terminal(provider, plan_a, provider.submit(plan_a, context=ctx_child_a))
        out_b, _ = _drive_to_terminal(provider, plan_b, provider.submit(plan_b, context=ctx_child_b))
        assert isinstance(out_a, Definitive)
        assert isinstance(out_b, Definitive)
        assert out_a.evidence != out_b.evidence

        lines = call_log.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

        # Repeated submit with the same (task, session, op, attempt, digest) reads durable state and NEVER re-invokes
        repeat_a = provider.submit(plan_a, context=ctx_child_a)
        assert isinstance(repeat_a, Definitive)
        validate_provider_result(plan_a, repeat_a)
        assert repeat_a.result == out_a.result
        assert len(call_log.read_text(encoding="utf-8").strip().splitlines()) == 2
    finally:
        runtime.shutdown()

    # Recreating runtime in a fresh instance still returns durable Definitive without re-running
    runtime2 = MCPRuntimeManager(root)
    try:
        provider2 = MCPToolProvider(
            root,
            "task_2",
            ws,
            step_desc,
            runtime2,
        )
        ctx_child_a, plan_a = _make_ctx_and_plan(
            ws,
            step_desc,
            {"tag": "shared_arg"},
            session_id="child_session_alpha",
            turn_task_id="same_turn_id",
            operation_id="same_op_id",
            attempt=1,
            tool_call_id="tc_a",
        )
        repeat_after_restart = provider2.submit(plan_a, context=ctx_child_a)
        assert isinstance(repeat_after_restart, Definitive)
        validate_provider_result(plan_a, repeat_after_restart)
        assert len(call_log.read_text(encoding="utf-8").strip().splitlines()) == 2
        assert runtime2._thread is None  # Did not even start the runtime thread
    finally:
        runtime2.shutdown()


def test_tool_error_is_definitive_media_is_materialized_and_timeout_is_unknown(tmp_path: Path) -> None:
    root = tmp_path / "state"
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    call_log = tmp_path / "calls.log"

    lib, _disc, frozen = _setup_stateful_server(
        root,
        timeout_seconds=10.0,
        extra_env={"FIXTURE_CALL_LOG": str(call_log)},
    )
    _seed_business_task(lib.store, "task_3", frozen)
    by_name = {d["name"]: d for d in frozen}
    media_desc = by_name["media_and_error"]
    step_desc = by_name["stateful_step"]

    runtime = MCPRuntimeManager(root)
    try:
        media_provider = MCPToolProvider(
            root,
            "task_3",
            ws,
            media_desc,
            runtime,
            wait_window_seconds=2.0,
        )
        step_provider = MCPToolProvider(
            root,
            "task_3",
            ws,
            step_desc,
            runtime,
            wait_window_seconds=0.05,
        )

        # 1. MCP is_error=True response settles as Definitive error (with secret redacted)
        ctx_err, plan_err = _make_ctx_and_plan(
            ws, media_desc, {"fail": True}, session_id="s1", operation_id="op_err", tool_call_id="tc_err"
        )
        out_err, _ = _drive_to_terminal(media_provider, plan_err, media_provider.submit(plan_err, context=ctx_err))
        assert isinstance(out_err, Definitive)
        assert out_err.result["status_code"] == "ERROR"
        assert "SYNTHETIC-SECRET-ALPHA-123" not in out_err.result["content"]
        assert "[REDACTED]" in out_err.result["content"]

        # 2. Media response materializes artifact under workspace/outputs/mcp/ and strips base64 from durable job/result
        ctx_img, plan_img = _make_ctx_and_plan(
            ws, media_desc, {"fail": False}, session_id="s1", operation_id="op_img", tool_call_id="tc_img"
        )
        out_img, _ = _drive_to_terminal(media_provider, plan_img, media_provider.submit(plan_img, context=ctx_img))
        assert isinstance(out_img, Definitive)
        assert out_img.result["status_code"] == "SUCCESS"
        img_payload = json.loads(out_img.result["content"])
        assert "iVBORw0KGgo" not in out_img.result["content"]
        artifacts = img_payload.get("artifacts") or []
        assert len(artifacts) == 1
        rel_path = artifacts[0]["path"]
        assert rel_path.startswith("outputs/mcp/")
        assert rel_path.endswith(".png")
        assert (ws / rel_path).is_file()
        assert (ws / rel_path).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")

        # 3. Post-dispatch timeout settles as Unknown AND any queued operation behind it fails pre-dispatch without reconnecting!
        lib.save({"server_id": "stateful-srv", "timeout_seconds": 1.2})
        ctx_to, plan_to = _make_ctx_and_plan(
            ws,
            step_desc,
            {"tag": "slow_timeout", "delay": 3.0},
            session_id="s1",
            operation_id="op_to",
            tool_call_id="tc_to",
        )
        sub_to = step_provider.submit(plan_to, context=ctx_to)
        assert isinstance(sub_to, Accepted)

        # Queue a second operation on the same session/server while the first is timing out
        ctx_after, plan_after = _make_ctx_and_plan(
            ws,
            step_desc,
            {"tag": "queued_behind_timeout", "delay": 0.0},
            session_id="s1",
            operation_id="op_after_to",
            tool_call_id="tc_after_to",
        )
        sub_after = step_provider.submit(plan_after, context=ctx_after)
        assert isinstance(sub_after, Accepted)

        out_to, _ = _drive_to_terminal(step_provider, plan_to, sub_to, timeout=10.0)
        assert isinstance(out_to, Unknown)
        assert "timed out after dispatch" in out_to.reason.lower()

        out_after, _ = _drive_to_terminal(step_provider, plan_after, sub_after, timeout=5.0)
        assert isinstance(out_after, Definitive)
        assert out_after.result["status_code"] == "ERROR"
        assert out_after.result["error_code"] == "connection_reset_after_unknown"

        lines_after_timeout = call_log.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines_after_timeout) == 1
        assert "queued_behind_timeout" not in call_log.read_text(encoding="utf-8")

        # Repeated submit of the Unknown operation must NOT replay
        repeat_to = step_provider.submit(plan_to, context=ctx_to)
        assert isinstance(repeat_to, Unknown)
        assert len(call_log.read_text(encoding="utf-8").strip().splitlines()) == 1

        views = mcp_run_views(runtime.store, "task_3")
        assert len(views) == 4
    finally:
        runtime.shutdown()


def test_queued_operation_cancelled_before_dispatch_never_executes(tmp_path: Path) -> None:
    root = tmp_path / "state"
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    call_log = tmp_path / "calls.log"

    lib, _disc, frozen = _setup_stateful_server(
        root,
        timeout_seconds=10.0,
        extra_env={"FIXTURE_CALL_LOG": str(call_log)},
    )
    _seed_business_task(lib.store, "task_cancel_queue", frozen)
    step_desc = next(d for d in frozen if d["name"] == "stateful_step")

    runtime = MCPRuntimeManager(root)
    try:
        provider = MCPToolProvider(
            root,
            "task_cancel_queue",
            ws,
            step_desc,
            runtime,
            wait_window_seconds=0.05,
        )

        # Submit op1 (takes ~0.8s so it occupies the server worker)
        ctx1, plan1 = _make_ctx_and_plan(
            ws,
            step_desc,
            {"tag": "first_in_flight", "delay": 0.8},
            session_id="s_q",
            operation_id="op_first",
            tool_call_id="tc_1",
        )
        sub1 = provider.submit(plan1, context=ctx1)
        assert isinstance(sub1, Accepted)
        validate_provider_handle(plan1, sub1.handle)

        # Submit op2 immediately on the same session/server so it sits in the queue behind op1
        ctx2, plan2 = _make_ctx_and_plan(
            ws,
            step_desc,
            {"tag": "second_cancelled", "delay": 0.0},
            session_id="s_q",
            operation_id="op_queued",
            tool_call_id="tc_2",
        )
        sub2 = provider.submit(plan2, context=ctx2)
        assert isinstance(sub2, Accepted)
        validate_provider_handle(plan2, sub2.handle)

        # Cancel op2 before op1 finishes
        cancelled_out = provider.cancel(sub2.handle)
        assert isinstance(cancelled_out, Definitive)
        validate_provider_result(plan2, cancelled_out, sub2.handle)
        assert cancelled_out.result["status_code"] == "ERROR"
        assert cancelled_out.result["error_code"] == "tool_cancelled"

        # Wait for op1 to complete
        final1, _ = _drive_to_terminal(provider, plan1, sub1, timeout=10.0)
        assert isinstance(final1, Definitive)
        assert final1.result["status_code"] == "SUCCESS"

        # Verify op2 NEVER ran on the server when the queue drained
        time.sleep(0.2)
        lines = call_log.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        assert "first_in_flight" in lines[0]
        assert "second_cancelled" not in call_log.read_text(encoding="utf-8")
    finally:
        runtime.shutdown()


def test_preflight_rejects_disabled_stale_changed_and_allows_credential_rotation(tmp_path: Path) -> None:
    root = tmp_path / "state"
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    call_log = tmp_path / "calls.log"

    lib, _disc, frozen = _setup_stateful_server(
        root,
        secret="INITIAL-SECRET-111",
        extra_env={"FIXTURE_CALL_LOG": str(call_log)},
    )
    _seed_business_task(lib.store, "task_preflight", frozen)
    step_desc = next(d for d in frozen if d["name"] == "stateful_step")

    runtime = MCPRuntimeManager(root)
    try:
        provider = MCPToolProvider(
            root,
            "task_preflight",
            ws,
            step_desc,
            runtime,
            wait_window_seconds=2.0,
        )

        # 1. Invalid arguments rejected before dispatch and durable job row is FINISHED/FAILED (result not NULL)
        ctx_bad, plan_bad = _make_ctx_and_plan(ws, step_desc, {}, operation_id="op_bad_arg", tool_call_id="tc_bad")
        out_bad = provider.submit(plan_bad, context=ctx_bad)
        assert isinstance(out_bad, Definitive)
        validate_provider_result(plan_bad, out_bad)
        assert out_bad.result["status_code"] == "ERROR"
        assert not call_log.exists()

        # Verify durable row has status == FAILED and result != None
        jobs_now = runtime.store.mcp_jobs("task_preflight")
        assert len(jobs_now) == 1
        assert jobs_now[0]["status"] == "FAILED"
        assert jobs_now[0]["result"] is not None

        # 2. Disabled tool rejected before dispatch
        lib.set_tool_enabled("stateful-srv", tool_name=step_desc["namespaced_name"], enabled=False)
        ctx_dis_t, plan_dis_t = _make_ctx_and_plan(
            ws, step_desc, {"tag": "no"}, operation_id="op_dis_tool", tool_call_id="tc_dt"
        )
        out_dis_t = provider.submit(plan_dis_t, context=ctx_dis_t)
        assert isinstance(out_dis_t, Definitive)
        validate_provider_result(plan_dis_t, out_dis_t)
        assert out_dis_t.result["error_code"] == "mcp_tool_disabled"
        lib.set_tool_enabled("stateful-srv", tool_name=step_desc["namespaced_name"], enabled=True)

        # 3. Disabled server rejected before dispatch
        lib.save({"server_id": "stateful-srv", "enabled": False})
        ctx_dis_s, plan_dis_s = _make_ctx_and_plan(
            ws, step_desc, {"tag": "no"}, operation_id="op_dis_srv", tool_call_id="tc_ds"
        )
        out_dis_s = provider.submit(plan_dis_s, context=ctx_dis_s)
        assert isinstance(out_dis_s, Definitive)
        validate_provider_result(plan_dis_s, out_dis_s)
        assert out_dis_s.result["error_code"] == "mcp_server_disabled"
        lib.save({"server_id": "stateful-srv", "enabled": True})

        # 4. Credential rotation marks discovery stale until retested, then succeeds after retest!
        lib.save(
            {
                "server_id": "stateful-srv",
                "env": {
                    "SYNTHETIC_STDIO_SECRET": "ROTATED-SECRET-222",
                    "FIXTURE_CALL_LOG": str(call_log),
                },
            }
        )
        ctx_stale, plan_stale = _make_ctx_and_plan(
            ws, step_desc, {"tag": "stale"}, operation_id="op_stale", tool_call_id="tc_st"
        )
        out_stale = provider.submit(plan_stale, context=ctx_stale)
        assert isinstance(out_stale, Definitive)
        validate_provider_result(plan_stale, out_stale)
        assert out_stale.result["error_code"] == "mcp_discovery_stale"

        # Retest after credential rotation
        lib.test("stateful-srv")
        ctx_rot, plan_rot = _make_ctx_and_plan(
            ws, step_desc, {"tag": "after_rotation"}, operation_id="op_rotated", tool_call_id="tc_rot"
        )
        out_rot, _ = _drive_to_terminal(provider, plan_rot, provider.submit(plan_rot, context=ctx_rot))
        assert isinstance(out_rot, Definitive)
        assert out_rot.result["status_code"] == "SUCCESS"
        assert "ROTATED-SECRET-222" not in out_rot.result["content"]
        assert "[REDACTED]" in out_rot.result["content"]

        # 5. Non-credential env change (e.g. MONKEY_HOME) changes endpoint_fingerprint -> rejected even after retest
        lib.save(
            {
                "server_id": "stateful-srv",
                "env": {
                    "SYNTHETIC_STDIO_SECRET": "ROTATED-SECRET-222",
                    "FIXTURE_CALL_LOG": str(call_log),
                    "MONKEY_HOME": "/tmp/other_destination",
                },
            }
        )
        lib.test("stateful-srv")
        ctx_ep, plan_ep = _make_ctx_and_plan(
            ws, step_desc, {"tag": "rerouted"}, operation_id="op_ep_changed", tool_call_id="tc_ep"
        )
        out_ep = provider.submit(plan_ep, context=ctx_ep)
        assert isinstance(out_ep, Definitive)
        validate_provider_result(plan_ep, out_ep)
        assert out_ep.result["error_code"] == "mcp_endpoint_changed"

        # 6. Legacy descriptor without endpoint_fingerprint requires exact connection_fingerprint or fails
        legacy_desc = deepcopy(step_desc)
        legacy_desc.pop("endpoint_fingerprint", None)
        _seed_business_task(lib.store, "task_legacy", [legacy_desc])
        legacy_provider = MCPToolProvider(
            root,
            "task_legacy",
            ws,
            legacy_desc,
            runtime,
        )
        ctx_leg, plan_leg = _make_ctx_and_plan(
            ws, legacy_desc, {"tag": "legacy"}, operation_id="op_legacy_changed", tool_call_id="tc_leg"
        )
        out_leg = legacy_provider.submit(plan_leg, context=ctx_leg)
        assert isinstance(out_leg, Definitive)
        validate_provider_result(plan_leg, out_leg)
        assert out_leg.result["error_code"] == "mcp_connection_changed"
    finally:
        runtime.shutdown()


def test_startup_cancellation_during_hang_init_is_bounded_and_cleans_up_process(tmp_path: Path) -> None:
    root = tmp_path / "state"
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    pid_file = tmp_path / "hang.pid"

    lib, _disc, frozen = _setup_stateful_server(
        root,
        server_id="hang-srv",
        timeout_seconds=10.0,
        extra_env={"FIXTURE_PID_FILE": str(pid_file)},
    )
    _seed_business_task(lib.store, "task_hang", frozen)
    step_desc = next(d for d in frozen if d["name"] == "stateful_step")

    # Point server args at hang_init in DB while keeping tested_fingerprint aligned so preflight passes and startup hangs
    pid_file.unlink(missing_ok=True)
    rec = lib.store.get_mcp_server("hang-srv")
    assert rec is not None
    rec["config"]["args"] = [FIXTURE_SCRIPT, "hang_init"]
    rec["config"]["timeout_seconds"] = 30.0
    from task_agent.mcp_library import _connection_fingerprint
    from task_agent.integrations import mcp_endpoint_fingerprint

    new_conn_fp = _connection_fingerprint(rec["transport"], rec["config"], rec["secrets"])
    new_ep_fp = mcp_endpoint_fingerprint(rec)
    rec["status"]["tested_fingerprint"] = new_conn_fp
    rec["status"]["stale"] = False
    with lib.store.connect() as conn:
        conn.execute(
            "UPDATE task_mcp_servers SET config=?, status=? WHERE server_id='hang-srv'",
            (json.dumps(rec["config"]), json.dumps(rec["status"])),
        )
    step_desc["connection_fingerprint"] = new_conn_fp
    step_desc["endpoint_fingerprint"] = new_ep_fp
    with lib.store.connect() as conn:
        conn.execute(
            "UPDATE tasks SET config_snapshot=? WHERE tid='task_hang'",
            (json.dumps({"mcp_tools": [step_desc]}),),
        )

    runtime = MCPRuntimeManager(root)
    try:
        provider = MCPToolProvider(
            root,
            "task_hang",
            ws,
            step_desc,
            runtime,
            wait_window_seconds=0.1,
        )
        ctx_h, plan_h = _make_ctx_and_plan(ws, step_desc, {"tag": "hang"}, operation_id="op_hang", tool_call_id="tc_h")
        sub_h = provider.submit(plan_h, context=ctx_h)
        assert isinstance(sub_h, Accepted)

        # Wait until hang_init child writes its PID
        deadline = time.time() + 5.0
        while not pid_file.exists() and time.time() < deadline:
            time.sleep(0.05)
        assert pid_file.exists()
        hang_pid = int(pid_file.read_text(encoding="utf-8").strip())
        assert _is_pid_running(hang_pid)

        # Cancel during connection initialization (before dispatch)
        cancelled = provider.cancel(sub_h.handle)
        assert isinstance(cancelled, Definitive)
        validate_provider_result(plan_h, cancelled, sub_h.handle)
        assert cancelled.result["status_code"] == "ERROR"
        assert cancelled.result["error_code"] == "tool_cancelled"

        # Process should be cleaned up promptly
        deadline = time.time() + 5.0
        while _is_pid_running(hang_pid) and time.time() < deadline:
            time.sleep(0.1)
        assert not _is_pid_running(hang_pid)
    finally:
        runtime.shutdown()
