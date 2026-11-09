"""End-to-end AppServer + deterministic model + official local MCP server smoke tests."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

workspace = Path(sys.argv[1]).resolve()
port = int(sys.argv[2])
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.chdir(workspace)

from cli import initialize  # noqa: E402
from models import Setting, database  # noqa: E402
from task_agent.deletion import DeletionConflict  # noqa: E402
from task_agent.service import TaskAgentService  # noqa: E402
import sqlite3  # noqa: E402

FIXTURE_SCRIPT = str((Path(__file__).parent / "mcp_test_server.py").resolve())
SYNTHETIC_MCP_SECRET = "SYNTHETIC_MCP_APP_SECRET_987654"
SYNTHETIC_LLM_KEY = "local-test-credential-mcp-appserver"


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
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _configure_settings(*, reviewer_model: str | None = "mock-reviewer-allow") -> None:
    setting = Setting.select().order_by(Setting.create_time.desc()).first()
    setting.data["llm_settings"] = {
        "VERSION": "2",
        "endpoints": [
            {
                "id": "mock-endpoint",
                "api_base": f"http://127.0.0.1:{port}/v1",
                "api_key": SYNTHETIC_LLM_KEY,
            }
        ],
        "backends": {
            "local": {
                "models": {
                    "mock-mcp-model": {
                        "id": "mock-mcp-model",
                        "enabled": True,
                        "endpoints": ["mock-endpoint"],
                        "function_call_available": True,
                        "context_length": 32768,
                        "max_output_tokens": 2048,
                        "supported_reasoning_efforts": ["low"],
                        "capabilities": {"reasoning_efforts": ["low"]},
                    },
                    "mock-reviewer-allow": {
                        "id": "mock-reviewer-allow",
                        "enabled": True,
                        "endpoints": ["mock-endpoint"],
                        "function_call_available": False,
                        "context_length": 16384,
                        "max_output_tokens": 1024,
                    },
                    "mock-reviewer-fail": {
                        "id": "mock-reviewer-fail",
                        "enabled": True,
                        "endpoints": ["mock-endpoint"],
                        "function_call_available": False,
                        "context_length": 16384,
                        "max_output_tokens": 1024,
                    },
                },
            },
        },
    }
    setting.data["custom_llms"] = {
        "local-test": ["mock-mcp-model", "mock-reviewer-allow", "mock-reviewer-fail"]
    }
    setting.data["model_preferences"] = {
        "default": {"model_provider": "_local__local-test", "model": "mock-mcp-model"}
    }
    if reviewer_model:
        setting.data["task_agent_approval"] = {
            "model_provider": "_local__local-test",
            "model": reviewer_model,
        }
    else:
        setting.data.pop("task_agent_approval", None)
    setting.save()
    database.close()


def _wait_status(
    service: TaskAgentService,
    tid: str,
    target_statuses: set[str],
    *,
    timeout: float = 25.0,
) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = service.get_task(tid)
        if last["task"]["status"] in target_statuses:
            return last
        time.sleep(0.15)
    raise AssertionError(f"Task {tid} did not reach {target_statuses}: {last}")


initialize()
_configure_settings(reviewer_model="mock-reviewer-allow")

pid_file = workspace / "mcp_server.pid"
call_log = workspace / "mcp_calls.log"

service = TaskAgentService(workspace)
try:
    # 1. Save and test official stdio MCP server
    service.save_mcp_server(
        {
            "server_id": "app_srv",
            "name": "App MCP Server",
            "transport": "stdio",
            "command": sys.executable,
            "args": [FIXTURE_SCRIPT, "runtime_stateful"],
            "env": {
                "SYNTHETIC_STDIO_SECRET": SYNTHETIC_MCP_SECRET,
                "FIXTURE_PID_FILE": str(pid_file),
                "FIXTURE_CALL_LOG": str(call_log),
            },
            "timeout_seconds": 10.0,
            "enabled": True,
        }
    )
    tested = service.test_mcp_server({"server_id": "app_srv"})
    by_name = {t["name"]: t["namespaced_name"] for t in tested["tools"]}
    ns_step = by_name["stateful_step"]
    ns_peer = by_name["peer_info"]
    ns_media = by_name["media_and_error"]

    # Clear pid_file from discovery test
    pid_file.unlink(missing_ok=True)
    call_log.unlink(missing_ok=True)

    # Save profiles for ask, auto, and full modes (selecting ONLY ns_step and ns_media, leaving ns_peer unselected!)
    for mode in ("ask", "auto", "full"):
        service.save_profile(
            {
                "agent_id": f"mcp_{mode}",
                "name": f"MCP {mode.upper()} Agent",
                "description": f"Tests {mode} mode",
                "instructions": "Execute requested MCP scenarios.",
                "max_cycles": 8,
                "allow_file_writes": False,
                "allow_shell": False,
                "allow_sub_agents": True,
                "permission_mode": mode,
                "mcp_tool_ids": [ns_step, ns_media],
            }
        )

    # --- Scenario A: ask mode DENY -> zero server calls ---
    service.create_task(
        {
            "input_id": "task_ask_deny",
            "turn_input_id": "t1",
            "goal": "SCENARIO:SINGLE_STEP tag=denied_call",
            "agent_id": "mcp_ask",
            "model_provider": "_local__local-test",
            "model": "mock-mcp-model",
            "reasoning_effort": "low",
        }
    )
    wait_deny = _wait_status(service, "task_ask_deny", {"WAITING_FOR_APPROVAL"})
    pending_deny = wait_deny["state"]["pendingInteraction"]
    assert pending_deny["kind"] == "approval"
    assert pending_deny.get("display_name") == "App MCP Server: Stateful Step"
    # Even though stateful_step has readOnlyHint=True, ask mode MUST pause for approval!
    assert not call_log.exists()
    service.approve(
        {
            "task_id": "task_ask_deny",
            "turn_id": wait_deny["task"]["current_turn_id"],
            "request_id": pending_deny["requestId"],
            "decision": "deny",
        }
    )
    done_deny = _wait_status(service, "task_ask_deny", {"COMPLETED"})
    assert not call_log.exists()
    assert done_deny["mcp_runs"] == []

    # --- Scenario B: ask mode ALLOW + two sequential stateful calls share PID/state + child session scope ---
    service.create_task(
        {
            "input_id": "task_ask_allow",
            "turn_input_id": "t1",
            "goal": "SCENARIO:TWO_STEPS_AND_CHILD",
            "agent_id": "mcp_ask",
            "model_provider": "_local__local-test",
            "model": "mock-mcp-model",
            "reasoning_effort": "low",
        }
    )
    def _wait_next_approval(tid: str, seen_req_ids: set[str]) -> dict[str, Any]:
        deadline = time.time() + 25.0
        last: dict[str, Any] = {}
        while time.time() < deadline:
            last = service.get_task(tid)
            pend = (last.get("state") or {}).get("pendingInteraction") or {}
            if last["task"]["status"] == "WAITING_FOR_APPROVAL" and pend.get("requestId") and pend["requestId"] not in seen_req_ids:
                seen_req_ids.add(pend["requestId"])
                return last
            time.sleep(0.15)
        raise AssertionError(f"Did not receive next approval for {tid}: {last}")

    seen_reqs: set[str] = set()
    w1 = _wait_next_approval("task_ask_allow", seen_reqs)
    service.approve(
        {
            "task_id": "task_ask_allow",
            "turn_id": w1["task"]["current_turn_id"],
            "request_id": w1["state"]["pendingInteraction"]["requestId"],
            "decision": "allow",
        }
    )
    w2 = _wait_next_approval("task_ask_allow", seen_reqs)
    service.approve(
        {
            "task_id": "task_ask_allow",
            "turn_id": w2["task"]["current_turn_id"],
            "request_id": w2["state"]["pendingInteraction"]["requestId"],
            "decision": "allow",
        }
    )
    w3 = _wait_next_approval("task_ask_allow", seen_reqs)
    assert "/child/" in w3["state"]["pendingInteraction"]["sessionId"]
    assert w3["state"]["pendingInteraction"].get("display_name") == "App MCP Server: Stateful Step"
    service.approve(
        {
            "task_id": "task_ask_allow",
            "turn_id": w3["task"]["current_turn_id"],
            "request_id": w3["state"]["pendingInteraction"]["requestId"],
            "decision": "allow",
        }
    )
    done_allow = _wait_status(service, "task_ask_allow", {"COMPLETED"})
    assert len(done_allow["mcp_runs"]) == 3
    log_lines = call_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(log_lines) == 3
    # First two parent calls share the exact same PID and sequential call numbers 1 and 2
    p1_pid, p1_cnt, p1_tag = log_lines[0].split(":")
    p2_pid, p2_cnt, p2_tag = log_lines[1].split(":")
    c1_pid, c1_cnt, c1_tag = log_lines[2].split(":")
    assert p1_pid == p2_pid
    assert (p1_cnt, p2_cnt) == ("1", "2")
    assert (p1_tag, p2_tag, c1_tag) == ("step_one", "step_two", "child_step")
    # Distinct session_ids recorded in mcp_runs for parent vs child
    sessions_used = {r["session_id"] for r in done_allow["mcp_runs"]}
    assert "task_ask_allow" in sessions_used
    assert any("/child/" in s for s in sessions_used)
    # Display names populated on timeline
    mcp_timeline = [e for e in done_allow["timeline"] if e.get("tool_name") == ns_step]
    assert mcp_timeline and mcp_timeline[0].get("display_name") == "App MCP Server: Stateful Step"
    # After turn completes, owned server processes for both parent and child are closed
    for pid_str in {p1_pid, c1_pid}:
        deadline = time.time() + 5.0
        while _is_pid_running(int(pid_str)) and time.time() < deadline:
            time.sleep(0.1)
        assert not _is_pid_running(int(pid_str))

    # --- Scenario C: auto mode with configured reviewer ALLOW + media preview + tool error ---
    call_log.unlink(missing_ok=True)
    service.create_task(
        {
            "input_id": "task_auto_media",
            "turn_input_id": "t1",
            "goal": "SCENARIO:MEDIA_AND_TOOL_ERROR",
            "agent_id": "mcp_auto",
            "model_provider": "_local__local-test",
            "model": "mock-mcp-model",
            "reasoning_effort": "low",
        }
    )
    done_media = _wait_status(service, "task_auto_media", {"COMPLETED"})
    assert len(done_media["mcp_runs"]) == 2
    assert len(done_media["risk_reviews"]) >= 2
    assert all(r["status"] == "approved" for r in done_media["risk_reviews"])

    # Verify materialized PNG artifact is browsable and previewable via task files API
    media_runs = [r for r in done_media["mcp_runs"] if r.get("artifacts")]
    assert len(media_runs) == 1
    art_path = media_runs[0]["artifacts"][0]["path"]
    assert art_path.startswith("outputs/mcp/")
    from task_agent import files as task_files
    listed_files = task_files.list_files(service, "task_auto_media")
    assert any(f["path"] == art_path for f in listed_files["files"]), listed_files
    preview = task_files.preview_file(service, "task_auto_media", art_path)
    assert preview["kind"] == "image"
    assert preview["url"].startswith("data:image/png;base64,")

    # Verify tool error run is recorded with status FAILED and error_code mcp_tool_error
    err_runs = [r for r in done_media["mcp_runs"] if r["status"] == "FAILED"]
    assert len(err_runs) == 1
    assert err_runs[0]["error_code"] == "mcp_tool_error"

    # --- Scenario D: auto mode when reviewer fails OR argument contains MCP secret -> manual approval wait ---
    _configure_settings(reviewer_model="mock-reviewer-fail")
    service.create_task(
        {
            "input_id": "task_auto_fallback",
            "turn_input_id": "t1",
            "goal": "SCENARIO:SINGLE_STEP tag=fallback_manual",
            "agent_id": "mcp_auto",
            "model_provider": "_local__local-test",
            "model": "mock-mcp-model",
            "reasoning_effort": "low",
        }
    )
    wait_fb = _wait_status(service, "task_auto_fallback", {"WAITING_FOR_APPROVAL"})
    assert wait_fb["risk_reviews"][0]["status"] == "manual"
    service.approve(
        {
            "task_id": "task_auto_fallback",
            "turn_id": wait_fb["task"]["current_turn_id"],
            "request_id": wait_fb["state"]["pendingInteraction"]["requestId"],
            "decision": "allow",
        }
    )
    _wait_status(service, "task_auto_fallback", {"COMPLETED"})



    # --- Scenario E: full mode executes without human wait; post-dispatch timeout settles as UNKNOWN and blocks deletion ---
    call_log.unlink(missing_ok=True)
    srv_rec = service.store.get_mcp_server("app_srv")
    srv_rec["config"]["timeout_seconds"] = 3.0
    with service.store.connect() as conn:
        conn.execute(
            "UPDATE task_mcp_servers SET config=? WHERE server_id='app_srv'",
            (json.dumps(srv_rec["config"]),),
        )
    service.create_task(
        {
            "input_id": "task_full_timeout",
            "turn_input_id": "t1",
            "goal": "SCENARIO:SLOW_TIMEOUT",
            "agent_id": "mcp_full",
            "model_provider": "_local__local-test",
            "model": "mock-mcp-model",
            "reasoning_effort": "low",
        }
    )
    deadline = time.time() + 15.0
    done_to: dict[str, Any] = {}
    while time.time() < deadline:
        done_to = service.get_task("task_full_timeout")
        if done_to["mcp_runs"] and done_to["mcp_runs"][0]["status"] == "UNKNOWN":
            break
        time.sleep(0.2)
    assert len(done_to["mcp_runs"]) == 1, done_to
    assert done_to["mcp_runs"][0]["status"] == "UNKNOWN", done_to["mcp_runs"]
    assert done_to["mcp_runs"][0]["dispatch_uncertain"] is True
    assert done_to["mcp_runs"][0]["unknown_code"] == "call_timeout"
    # Call log has exactly 1 entry (never replayed across polling!)
    time.sleep(0.5)
    _ = service.get_task("task_full_timeout")
    assert len(call_log.read_text(encoding="utf-8").strip().splitlines()) == 1
    # Cancel the parked turn after post-dispatch timeout -> settles as INTERRUPTED and records op_unknown
    service.act(
        {
            "task_id": "task_full_timeout",
            "turn_id": done_to["task"]["current_turn_id"],
            "action_id": "cancel_to",
            "action": {"kind": "cancel"},
        }
    )
    done_to = _wait_status(service, "task_full_timeout", {"INTERRUPTED"}, timeout=15.0)
    to_tools = [e for e in done_to["timeline"] if e.get("kind") == "tool" and e.get("tool_name") == ns_step]
    assert to_tools and to_tools[0]["status"] == "unknown"

    # Wait for engine lease to clear, then verify deletion is blocked by active_mcp because outcome is UNKNOWN
    time.sleep(0.3)
    try:
        service.delete_task(
            {
                "task_id": "task_full_timeout",
                "expected_updated_at": service.get_task("task_full_timeout", cached=True)["task"]["updated_at"],
            }
        )
    except DeletionConflict as exc:
        assert exc.code in {"active_mcp", "engine_busy"}
    else:
        raise AssertionError("Expected DeletionConflict for task with UNKNOWN post-dispatch MCP job")

    # Restore timeout_seconds and test pre-dispatch failure (changed endpoint) is deletable once task finishes
    service.save_mcp_server(
        {
            "server_id": "app_srv",
            "timeout_seconds": 10.0,
            "env": {
                "SYNTHETIC_STDIO_SECRET": SYNTHETIC_MCP_SECRET,
                "FIXTURE_PID_FILE": str(pid_file),
                "FIXTURE_CALL_LOG": str(call_log),
                "MONKEY_HOME": "/tmp/changed_destination_after_freeze",
            },
        }
    )
    service.test_mcp_server({"server_id": "app_srv"})

    # Send follow-up on task_ask_deny (which froze the old endpoint) in full mode or create a task before endpoint change:
    # task_ask_deny already froze the old endpoint! Let's send a follow-up on task_ask_allow and approve it -> preflight rejects with mcp_endpoint_changed!
    call_log.unlink(missing_ok=True)
    service.send_message(
        {
            "task_id": "task_ask_allow",
            "input_id": "t2",
            "text": "SCENARIO:SINGLE_STEP tag=after_endpoint_change",
        }
    )
    w_ep = _wait_status(service, "task_ask_allow", {"WAITING_FOR_APPROVAL"})
    service.approve(
        {
            "task_id": "task_ask_allow",
            "turn_id": w_ep["task"]["current_turn_id"],
            "request_id": w_ep["state"]["pendingInteraction"]["requestId"],
            "decision": "allow",
        }
    )
    done_ep = _wait_status(service, "task_ask_allow", {"COMPLETED"})
    assert not call_log.exists()
    assert any(r["error_code"] == "mcp_endpoint_changed" for r in done_ep["mcp_runs"])

    # Delete completed task_ask_allow (has FINISHED and pre-dispatch FAILED mcp_jobs) -> succeeds and purges task_mcp_jobs!
    for _ in range(30):
        try:
            del_res = service.delete_task(
                {
                    "task_id": "task_ask_allow",
                    "expected_updated_at": service.get_task("task_ask_allow", cached=True)["task"]["updated_at"],
                }
            )
            assert del_res["deleted"] is True
            break
        except DeletionConflict as exc:
            if exc.code != "engine_busy":
                raise
            time.sleep(0.15)
    else:
        raise AssertionError("task_ask_allow never became deletable")
    assert service.store.mcp_jobs("task_ask_allow") == []

    # Verify cached get_task and list_tasks never start any MCP server process
    pid_file.unlink(missing_ok=True)
    _ = service.list_tasks()
    _ = service.get_task("task_auto_media", cached=True)
    assert not pid_file.exists()
finally:
    service.stop()

# --- Scenario F: Restart AppServer while a dispatched slow MCP call is in flight -> settles as Unknown without duplicate execution ---
service_restart = TaskAgentService(workspace)
try:
    service_restart.save_mcp_server(
        {
            "server_id": "app_srv",
            "timeout_seconds": 15.0,
            "env": {
                "SYNTHETIC_STDIO_SECRET": SYNTHETIC_MCP_SECRET,
                "FIXTURE_PID_FILE": str(pid_file),
                "FIXTURE_CALL_LOG": str(call_log),
            },
        }
    )
    service_restart.test_mcp_server({"server_id": "app_srv"})
    call_log.unlink(missing_ok=True)
    pid_file.unlink(missing_ok=True)

    service_restart.create_task(
        {
            "input_id": "task_restart_inflight",
            "turn_input_id": "t1",
            "goal": "SCENARIO:SLOW_INFLIGHT",
            "agent_id": "mcp_full",
            "model_provider": "_local__local-test",
            "model": "mock-mcp-model",
            "reasoning_effort": "low",
        }
    )
    deadline = time.time() + 15.0
    while (not call_log.exists() or not call_log.read_text(encoding="utf-8").strip()) and time.time() < deadline:
        time.sleep(0.05)
    assert call_log.exists() and len(call_log.read_text(encoding="utf-8").strip().splitlines()) == 1
finally:
    service_restart.stop()

service_resumed = TaskAgentService(workspace)
try:
    deadline = time.time() + 15.0
    done_resumed: dict[str, Any] = {}
    while time.time() < deadline:
        done_resumed = service_resumed.get_task("task_restart_inflight")
        if done_resumed["mcp_runs"] and done_resumed["mcp_runs"][0]["status"] == "UNKNOWN":
            break
        time.sleep(0.2)
    assert len(call_log.read_text(encoding="utf-8").strip().splitlines()) == 1
    assert len(done_resumed["mcp_runs"]) == 1
    assert done_resumed["mcp_runs"][0]["status"] == "UNKNOWN"
    assert done_resumed["mcp_runs"][0]["dispatch_uncertain"] is True
    service_resumed.act(
        {
            "task_id": "task_restart_inflight",
            "turn_id": done_resumed["task"]["current_turn_id"],
            "action_id": "cancel_inf",
            "action": {"kind": "cancel"},
        }
    )
    done_resumed = _wait_status(service_resumed, "task_restart_inflight", {"INTERRUPTED"}, timeout=15.0)
    assert len(call_log.read_text(encoding="utf-8").strip().splitlines()) == 1
finally:
    service_resumed.stop()

# Verify no synthetic MCP secret or LLM key leaked into business DB or sessions.db
for db_file in (workspace / "data" / "task-agent" / "tasks.db", workspace / "data" / "task-agent" / "sessions.db"):
    if db_file.exists():
        with sqlite3.connect(str(db_file)) as conn_check:
            tables = [
                r[0]
                for r in conn_check.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
            for tbl in tables:
                if tbl == "task_mcp_servers":
                    continue
                rows_text = "\n".join(
                    str(r) for r in conn_check.execute(f"SELECT * FROM {tbl}").fetchall()
                )
                assert SYNTHETIC_MCP_SECRET not in rows_text, f"Secret leaked in {db_file.name}:{tbl}"
                assert SYNTHETIC_LLM_KEY not in rows_text, f"LLM key leaked in {db_file.name}:{tbl}"
                assert "iVBORw0KGgo" not in rows_text, f"Base64 image leaked in {db_file.name}:{tbl}"

print(json.dumps({"passed": True}, ensure_ascii=False))
