from __future__ import annotations

import base64
from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import socket
import sys
import threading
import time

import anyio
import pytest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import uvicorn

from task_agent.mcp_library import (
    MCPLibrary,
    MCPLibraryError,
    MCPToolRegistry,
    _classify_transport_error,
    _format_call_tool_result,
    _quiet_mcp_loggers,
    build_mcp_function_tool,
    namespace_mcp_tool_name,
    validate_mcp_input_schema,
)
from task_agent.service import TaskConflict
from task_agent.store import BusinessStore, SCHEMA_VERSION
from vv_agent.tools.argument_validation import validate_tool_arguments
from vv_agent.types import ToolCall
import mcp_types as types

from mcp_test_server import create_http_mcp_server


FIXTURE_SCRIPT = str(Path(__file__).with_name("mcp_test_server.py").resolve())


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class _AuthGateMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        expected_header: str,
        expected_query_token: str | None = None,
        query_required_path: str | None = None,
    ):
        super().__init__(app)
        self.expected_header = expected_header
        self.expected_query_token = expected_query_token
        self.query_required_path = query_required_path

    async def dispatch(self, request, call_next):
        auth = request.headers.get("X-MCP-Auth") or request.headers.get("Authorization")
        if auth != self.expected_header:
            return JSONResponse({"error": f"Unauthorized: header={auth}"}, status_code=401)
        if self.expected_query_token is not None:
            if self.query_required_path is None or request.url.path == self.query_required_path:
                if request.query_params.get("api_key") != self.expected_query_token:
                    return JSONResponse({"error": "Invalid query token"}, status_code=403)
        return await call_next(request)


@contextmanager
def run_asgi_server(app):
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="critical", lifespan="on")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10.0
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5.0)


def _pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == STILL_ACTIVE
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def test_schema_v8_crud_search_optimistic_concurrency_and_secret_only_partial_updates(tmp_path):
    task_root = tmp_path / "task-agent"
    lib = MCPLibrary(task_root)
    with lib.store.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION

    stdio_saved = lib.save(
        {
            "server_id": "local_stdio",
            "name": "Local Stdio Server",
            "description": "Runs local python tools",
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-u", FIXTURE_SCRIPT, "paginated"],
            "cwd": str(tmp_path),
            "env": {"SYNTHETIC_STDIO_SECRET": "stdio-secret-value-123", "SECOND_KEY": "second-secret-456"},
            "timeout_seconds": 15,
        }
    )
    assert stdio_saved["server_id"] == "local_stdio"
    assert stdio_saved["env_keys"] == ["SECOND_KEY", "SYNTHETIC_STDIO_SECRET"]
    assert stdio_saved["has_env"] is True
    assert "stdio-secret-value-123" not in json.dumps(stdio_saved)
    assert "second-secret-456" not in json.dumps(stdio_saved)

    # Secret-only, args-only, description-only, timeout-only, and clear-only updates on existing server:
    desc_only = lib.save({"server_id": "local_stdio", "description": "Only description changed"})
    assert desc_only["description"] == "Only description changed"
    assert desc_only["command"] == sys.executable

    timeout_only = lib.save({"server_id": "local_stdio", "timeout_seconds": 25})
    assert timeout_only["timeout_seconds"] == 25.0

    args_only = lib.save({"server_id": "local_stdio", "args": ["-u", FIXTURE_SCRIPT, "other"]})
    assert args_only["args"] == ["-u", FIXTURE_SCRIPT, "other"]

    lib.save({"server_id": "local_stdio", "env": {"SECOND_KEY": "updated-second-secret"}})
    assert lib.store.get_mcp_server("local_stdio")["secrets"]["env"]["SECOND_KEY"] == "updated-second-secret"
    assert lib.store.get_mcp_server("local_stdio")["secrets"]["env"]["SYNTHETIC_STDIO_SECRET"] == "stdio-secret-value-123"

    clear_env_only = lib.save({"server_id": "local_stdio", "clear_env_keys": ["SECOND_KEY"]})
    assert clear_env_only["env_keys"] == ["SYNTHETIC_STDIO_SECRET"]

    # Remote HTTP server with URL query auth and case-insensitive header replacement/clearing
    http_saved = lib.save(
        {
            "server_id": "remote_http",
            "name": "Remote Streamable Server",
            "description": "Remote HTTP server",
            "transport": "streamable_http",
            "url": "https://example.invalid/mcp?api_key=query-secret-789&mode=fast",
            "headers": {"X-Key": "synthetic-old-private", "X-Custom": "custom-secret-xyz"},
            "timeout_seconds": 20,
        }
    )
    assert http_saved["display_url"] == "https://example.invalid/mcp?api_key=%2A%2A%2A&mode=%2A%2A%2A"
    assert http_saved["header_keys"] == ["X-Custom", "X-Key"]

    # Secret-only header update (case-insensitive replacement of X-Key with x-key)
    header_updated = lib.save({"server_id": "remote_http", "headers": {"x-key": "synthetic-new-private"}})
    assert header_updated["header_keys"] == ["X-Custom", "x-key"]
    assert lib.store.get_mcp_server("remote_http")["secrets"]["headers"] == {
        "X-Custom": "custom-secret-xyz",
        "x-key": "synthetic-new-private",
    }

    # Case-insensitive clear_header_keys-only update
    header_cleared = lib.save({"server_id": "remote_http", "clear_header_keys": ["x-custom"]})
    assert header_cleared["header_keys"] == ["x-key"]
    assert lib.store.get_mcp_server("remote_http")["secrets"]["headers"] == {"x-key": "synthetic-new-private"}

    # Reconstruct library from disk and make an unrelated edit (omitting url, headers, env)
    reloaded = MCPLibrary(task_root, store=BusinessStore(task_root / "tasks.db"))
    assert [s["server_id"] for s in reloaded.list(search="streamable")] == ["remote_http"]
    assert [s["server_id"] for s in reloaded.list(search="local_stdio")] == ["local_stdio"]

    edited_http = reloaded.save(
        {
            "server_id": "remote_http",
            "name": "Remote Streamable Renamed",
            "description": "Updated description without resending secrets",
            "transport": "streamable_http",
            "url": "",
            "headers": {"x-key": ""},
            "expected_updated_at": header_cleared["updated_at"],
        }
    )
    assert edited_http["name"] == "Remote Streamable Renamed"
    assert edited_http["header_keys"] == ["x-key"]
    raw_stored_http = reloaded.store.get_mcp_server("remote_http")
    assert raw_stored_http["secrets"]["url"] == "https://example.invalid/mcp?api_key=query-secret-789&mode=fast"
    assert raw_stored_http["secrets"]["headers"] == {"x-key": "synthetic-new-private"}

    with pytest.raises(TaskConflict):
        reloaded.save(
            {
                "server_id": "remote_http",
                "name": "Stale",
                "transport": "streamable_http",
                "expected_updated_at": http_saved["updated_at"],
            }
        )

    toggled = reloaded.save({"server_id": "remote_http", "enabled": False, "expected_updated_at": edited_http["updated_at"]})
    assert toggled["enabled"] is False
    assert reloaded.delete("remote_http", expected_updated_at=toggled["updated_at"]) == {
        "deleted": True,
        "server_id": "remote_http",
    }
    with pytest.raises(KeyError):
        reloaded.get("remote_http")


@pytest.mark.parametrize(
    "bad_payload,expected_code",
    [
        ({"server_id": "s1", "name": "Bad", "transport": "websocket", "url": "http://127.0.0.1:8000"}, "invalid_transport"),
        ({"server_id": "s1", "name": "Bad", "transport": "streamable_http", "url": "http://user:pass@127.0.0.1:8000/mcp"}, "url_userinfo_forbidden"),
        ({"server_id": "s1", "name": "Bad", "transport": "streamable_http", "url": "ftp://127.0.0.1/mcp"}, "invalid_url"),
        ({"server_id": "s1", "name": "Bad", "transport": "streamable_http", "url": "http://127.0.0.1/mcp#frag"}, "invalid_url"),
        ({"server_id": "s1", "name": "Bad", "transport": "stdio", "command": "python", "cwd": "relative/dir"}, "invalid_cwd"),
        ({"server_id": "s1", "name": "Bad", "transport": "stdio", "command": "python", "args": "not-a-list"}, "invalid_args"),
        ({"server_id": "s1", "name": "Bad", "transport": "stdio", "command": "python", "env": {"123_BAD": "v"}}, "invalid_env"),
        ({"server_id": "s1", "name": "Bad", "transport": "streamable_http", "url": "http://127.0.0.1/mcp", "headers": {"Host": "evil"}}, "invalid_header"),
        ({"server_id": "s1", "name": "Bad", "transport": "stdio", "command": "python", "timeout_seconds": 0}, "invalid_timeout"),
        ({"server_id": "s1", "name": "Bad", "transport": "stdio", "command": "python", "timeout_seconds": 999}, "invalid_timeout"),
    ],
)
def test_invalid_mcp_configurations_rejected(tmp_path, bad_payload, expected_code):
    lib = MCPLibrary(tmp_path / "task-agent")
    with pytest.raises(MCPLibraryError) as exc:
        lib.save(bad_payload)
    assert exc.value.code == expected_code
    assert lib.list() == []


def test_real_stdio_discovery_pagination_env_isolation_tool_sync_media_and_call_guards(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("AMBIENT_APP_SENTINEL", "ambient-secret-must-not-leak-999")
    pid_file = tmp_path / "stdio_child.pid"
    lib = MCPLibrary(tmp_path / "task-agent")

    saved = lib.save(
        {
            "server_id": "stdio_srv",
            "name": "Stdio Paginated Fixture",
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-u", FIXTURE_SCRIPT, "paginated"],
            "cwd": str(tmp_path),
            "env": {
                "SYNTHETIC_STDIO_SECRET": "stdio-private-token-777",
                "FIXTURE_PID_FILE": str(pid_file),
            },
            "timeout_seconds": 15,
        }
    )
    assert not pid_file.exists()
    assert saved["tool_count"] == 0

    with caplog.at_level(logging.DEBUG):
        discovered = lib.test("stdio_srv")

    assert pid_file.exists()
    child_pid = int(pid_file.read_text(encoding="utf-8").strip())
    deadline = time.monotonic() + 5.0
    while _pid_alive(child_pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _pid_alive(child_pid), "Stdio child process was not terminated after test()"

    assert discovered["last_test_status"] == "ok"
    assert discovered["discovery_stale"] is False
    assert discovered["tool_count"] == 3
    assert [t["name"] for t in discovered["tools"]] == ["echo_env", "slow_op", "media_and_error"]
    assert "stdio-private-token-777" not in json.dumps(discovered)
    assert "[REDACTED]" in discovered["tools"][0]["description"]
    assert "stdio-private-token-777" not in caplog.text

    # Disable one tool, re-run discovery, and verify per-tool enabled state is preserved.
    updated_tools = lib.set_tool_enabled("stdio_srv", tool_name="slow_op", enabled=False)
    assert updated_tools["enabled_tool_count"] == 2
    rediscovered = lib.test("stdio_srv")
    tool_map = {t["name"]: t for t in rediscovered["tools"]}
    assert tool_map["echo_env"]["enabled"] is True
    assert tool_map["slow_op"]["enabled"] is False

    # Call enabled tool and verify env isolation + secret redaction.
    call_res = lib.call_tool("stdio_srv", "echo_env", {"message": "hello", "extra": {"nested_open_key": 42}})
    assert call_res["is_error"] is False
    assert "ambient=ABSENT" in call_res["text"]
    assert "ambient-secret-must-not-leak-999" not in json.dumps(call_res)
    assert "stdio-private-token-777" not in json.dumps(call_res)
    assert call_res["structured_content"]["ambient"] == "ABSENT"
    assert call_res["structured_content"]["leaked_secret"] == "[REDACTED]"
    assert call_res["structured_content"]["extra"] == {"nested_open_key": 42}

    # Verify media & tool-level error returns:
    # Public call_tool omits base64 payload from public JSON while marking retained=True;
    # include_internal_media=True returns bounded internal_media for runtime materialization;
    # resource_link is never auto-fetched.
    pub_media = lib.call_tool("stdio_srv", "media_and_error", {"fail": False})
    assert pub_media["is_error"] is False
    assert "internal_media" not in pub_media
    img_block = next(b for b in pub_media["content"] if b["type"] == "image")
    assert img_block["retained"] is True and img_block["omitted"] is False
    assert "data" not in img_block and "data_base64" not in img_block
    link_block = next(b for b in pub_media["content"] if b["type"] == "resource_link")
    assert link_block["fetched"] is False

    internal_media_res = lib.call_tool("stdio_srv", "media_and_error", {"fail": False}, include_internal_media=True)
    assert len(internal_media_res["internal_media"]) == 1
    assert base64.b64decode(internal_media_res["internal_media"][0]["data_base64"]).startswith(b"\x89PNG")

    tool_err_res = lib.call_tool("stdio_srv", "media_and_error", {"fail": True})
    assert tool_err_res["is_error"] is True
    assert "[REDACTED]" in tool_err_res["text"]
    assert "stdio-private-token-777" not in json.dumps(tool_err_res)

    # Calling unknown tool or invalid arguments is rejected BEFORE network/process dispatch.
    pid_file.unlink(missing_ok=True)
    with pytest.raises(MCPLibraryError) as unknown_exc:
        lib.call_tool("stdio_srv", "nonexistent_tool", {})
    assert unknown_exc.value.code == "unknown_tool"
    assert unknown_exc.value.dispatch_uncertain is False
    assert not pid_file.exists()

    with pytest.raises(MCPLibraryError) as arg_exc:
        lib.call_tool("stdio_srv", "echo_env", {"extra": "not-an-object"})  # missing required 'message' & wrong type
    assert arg_exc.value.code == "invalid_tool_arguments"
    assert arg_exc.value.dispatch_uncertain is False
    assert not pid_file.exists()

    # Calling disabled tool is rejected before dispatch.
    with pytest.raises(MCPLibraryError) as disabled_exc:
        lib.call_tool("stdio_srv", "slow_op", {"delay": 0.01})
    assert disabled_exc.value.code == "tool_disabled"
    assert disabled_exc.value.dispatch_uncertain is False
    assert not pid_file.exists()

    # Unrelated name/description edit does NOT mark discovery stale.
    renamed = lib.save({"server_id": "stdio_srv", "name": "Stdio Renamed Only", "description": "Still valid"})
    assert renamed["discovery_stale"] is False
    assert renamed["last_test_status"] == "ok"
    assert len(lib.catalog()) == 1

    # Editing connection identity (command) marks discovery stale, hides from active catalog, and blocks call_tool until retested,
    # while retaining previously discovered tool metadata for inspection.
    stale_saved = lib.save(
        {
            "server_id": "stdio_srv",
            "command": str(tmp_path / "nonexistent_binary.exe"),
        }
    )
    assert stale_saved["discovery_stale"] is True
    assert stale_saved["last_test_status"] == "stale"
    assert stale_saved["tool_count"] == 3
    assert lib.catalog() == []
    with pytest.raises(MCPLibraryError) as stale_call_exc:
        lib.call_tool("stdio_srv", "echo_env", {"message": "blocked"})
    assert stale_call_exc.value.code == "discovery_stale"

    with pytest.raises(MCPLibraryError) as fail_exc:
        lib.test("stdio_srv")
    assert fail_exc.value.code == "executable_not_found"
    after_fail = lib.get("stdio_srv")
    assert after_fail["last_test_status"] == "error"
    assert after_fail["last_error"]["code"] == "executable_not_found"
    assert after_fail["tool_count"] == 3


def test_concurrent_edit_during_discovery_raises_conflict_and_never_overwrites_new_config(tmp_path, monkeypatch):
    lib = MCPLibrary(tmp_path / "task-agent")
    lib.save(
        {
            "server_id": "s",
            "name": "Concurrent Server",
            "transport": "streamable_http",
            "url": "http://127.0.0.1:9/old",
        }
    )

    async def fake_discover(record, *, previous_tools=None):
        # Simulate user saving a new URL while test('s') is in flight
        lib.save({"server_id": "s", "url": "http://127.0.0.1:9/new"})
        return {
            "protocol_version": "2025-11-25",
            "server_info": {"name": "old", "version": "1.0"},
            "tools": [
                {
                    "name": "old_tool",
                    "namespaced_name": namespace_mcp_tool_name("s", "old_tool"),
                    "title": "old_tool",
                    "description": "from old server",
                    "input_schema": {"type": "object", "properties": {}},
                    "annotations": {},
                    "enabled": True,
                }
            ],
        }

    monkeypatch.setattr("task_agent.mcp_library.discover_mcp_server_tools_async", fake_discover)
    with pytest.raises(TaskConflict):
        lib.test("s")

    current = lib.get("s")
    assert current["display_url"] == "http://127.0.0.1:9/new"
    assert current["tools"] == []
    assert current["last_test_status"] != "ok"


def test_real_streamable_http_and_sse_discovery_auth_reload_and_calls(tmp_path, caplog):
    mcp_server = create_http_mcp_server()
    streamable_app = mcp_server.streamable_http_app()
    streamable_app.add_middleware(
        _AuthGateMiddleware,
        expected_header="Bearer streamable-secret-token",
        expected_query_token="url-query-secret-111",
    )
    sse_app = mcp_server.sse_app()
    sse_app.add_middleware(
        _AuthGateMiddleware,
        expected_header="Bearer sse-secret-token",
        expected_query_token="sse-query-secret-222",
        query_required_path="/sse",
    )

    lib = MCPLibrary(tmp_path / "task-agent")

    with run_asgi_server(streamable_app) as http_base, run_asgi_server(sse_app) as sse_base:
        lib.save(
            {
                "server_id": "http_srv",
                "name": "Streamable HTTP Server",
                "transport": "streamable_http",
                "url": f"{http_base}/mcp?api_key=url-query-secret-111",
                "headers": {"Authorization": "Bearer streamable-secret-token"},
                "timeout_seconds": 15,
            }
        )
        reloaded = MCPLibrary(tmp_path / "task-agent", store=BusinessStore(tmp_path / "task-agent" / "tasks.db"))
        reloaded.save(
            {
                "server_id": "http_srv",
                "name": "Streamable HTTP Server Edited",
                "transport": "streamable_http",
            }
        )
        http_tested = reloaded.test("http_srv")
        assert http_tested["last_test_status"] == "ok"
        assert {t["name"] for t in http_tested["tools"]} == {"add_numbers", "inspect_payload"}
        assert "url-query-secret-111" not in json.dumps(http_tested)
        assert "streamable-secret-token" not in json.dumps(http_tested)

        call_out = reloaded.call_tool("http_srv", "add_numbers", {"a": 7, "b": 8})
        assert call_out["is_error"] is False
        assert "15" in call_out["text"]

        reloaded.save(
            {
                "server_id": "sse_srv",
                "name": "SSE Server",
                "transport": "sse",
                "url": f"{sse_base}/sse?api_key=sse-query-secret-222",
                "headers": {"Authorization": "Bearer sse-secret-token", "X-Extra": "secret-token-http-999"},
                "timeout_seconds": 15,
            }
        )
        sse_tested = reloaded.test("sse_srv")
        assert sse_tested["last_test_status"] == "ok"
        assert {t["name"] for t in sse_tested["tools"]} == {"add_numbers", "inspect_payload"}
        sse_call = reloaded.call_tool("sse_srv", "add_numbers", {"a": 10, "b": 20})
        assert sse_call["is_error"] is False
        assert "30" in sse_call["text"]
        assert "secret-token-http-999" not in json.dumps(sse_call)
        assert "[REDACTED]" in sse_call["text"]

        reloaded.save(
            {
                "server_id": "bad_auth_srv",
                "name": "Bad Auth Server",
                "transport": "streamable_http",
                "url": f"{http_base}/mcp?api_key=wrong-query-secret-333",
                "headers": {"Authorization": "Bearer wrong-header-secret-444"},
                "timeout_seconds": 10,
            }
        )
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(MCPLibraryError) as auth_exc:
                reloaded.test("bad_auth_srv")
        assert auth_exc.value.code == "authentication_failed"
        assert "wrong-query-secret-333" not in str(auth_exc.value)
        assert "wrong-header-secret-444" not in str(auth_exc.value)
        assert "wrong-query-secret-333" not in caplog.text
        assert "wrong-header-secret-444" not in caplog.text


def test_stdio_timeout_process_cleanup_and_dispatch_uncertainty(tmp_path):
    lib = MCPLibrary(tmp_path / "task-agent")
    hang_pid_file = tmp_path / "hang.pid"

    lib.save(
        {
            "server_id": "hang_srv",
            "name": "Hang Init Server",
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-u", FIXTURE_SCRIPT, "hang_init"],
            "env": {"FIXTURE_PID_FILE": str(hang_pid_file)},
            "timeout_seconds": 1.5,
        }
    )
    with pytest.raises(MCPLibraryError) as init_exc:
        lib.test("hang_srv")
    assert init_exc.value.code == "timeout"
    assert init_exc.value.dispatch_uncertain is False
    if hang_pid_file.exists():
        hang_pid = int(hang_pid_file.read_text(encoding="utf-8").strip())
        deadline = time.monotonic() + 5.0
        while _pid_alive(hang_pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not _pid_alive(hang_pid), "Hanging stdio process was not terminated on timeout"

    call_pid_file = tmp_path / "call_timeout.pid"
    lib.save(
        {
            "server_id": "slow_call_srv",
            "name": "Slow Call Server",
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-u", FIXTURE_SCRIPT, "paginated"],
            "env": {"FIXTURE_PID_FILE": str(call_pid_file)},
            "timeout_seconds": 10,
        }
    )
    lib.test("slow_call_srv")
    dispatched_flag = []
    with pytest.raises(MCPLibraryError) as call_exc:
        lib.call_tool(
            "slow_call_srv",
            "slow_op",
            {"delay": 15.0},
            timeout_seconds=3.0,
            on_dispatched=lambda: dispatched_flag.append(True),
        )
    assert dispatched_flag == [True]
    assert call_exc.value.code == "timeout"
    assert call_exc.value.dispatch_uncertain is True
    call_pid = int(call_pid_file.read_text(encoding="utf-8").strip())
    deadline = time.monotonic() + 5.0
    while _pid_alive(call_pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _pid_alive(call_pid), "Timed-out tool call child process was not terminated"


@pytest.mark.parametrize(
    "mode,expected_code",
    [
        ("infinite_cursor", "invalid_pagination_cursor"),
        ("external_ref", "external_schema_ref_forbidden"),
        ("duplicate_tools", "duplicate_tool_name"),
        ("secret_in_schema", "secret_in_tool_schema"),
        ("secret_in_name", "secret_in_tool_name"),
    ],
)
def test_discovery_rejects_cursor_loops_external_refs_duplicate_tools_and_secret_bearing_contracts(
    tmp_path, mode, expected_code, caplog
):
    lib = MCPLibrary(tmp_path / "task-agent")
    lib.save(
        {
            "server_id": f"bad_{mode}",
            "name": f"Bad {mode}",
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-u", FIXTURE_SCRIPT, mode],
            "env": {"SYNTHETIC_STDIO_SECRET": "contract-secret-token-888"},
            "timeout_seconds": 10,
        }
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(MCPLibraryError) as exc:
            lib.test(f"bad_{mode}")
    assert exc.value.code == expected_code
    assert "contract-secret-token-888" not in str(exc.value)
    assert "contract-secret-token-888" not in json.dumps(lib.get(f"bad_{mode}"))
    assert "contract-secret-token-888" not in caplog.text


def test_deterministic_case_sensitive_order_independent_namespace_and_collision_rejection():
    # Case-sensitive distinction for both server_id and tool_name
    assert namespace_mcp_tool_name("A", "echo") != namespace_mcp_tool_name("a", "echo")
    assert namespace_mcp_tool_name("srv", "Echo") != namespace_mcp_tool_name("srv", "echo")
    assert namespace_mcp_tool_name("my-server", "read-item") != namespace_mcp_tool_name("my_server", "read_item")
    assert namespace_mcp_tool_name("srv", "工具_A") != namespace_mcp_tool_name("srv", "工具_B")

    # Order independence regardless of discovery order or used_names contents
    pairs = [("A", "echo"), ("a", "echo"), ("srv", "Echo"), ("srv", "echo"), ("s" * 50, "t" * 80)]
    used_forward: set[str] = set()
    forward = [namespace_mcp_tool_name(s, t, used_forward) for s, t in pairs]
    used_reverse: set[str] = set()
    reverse = list(reversed([namespace_mcp_tool_name(s, t, used_reverse) for s, t in reversed(pairs)]))
    assert forward == reverse
    assert all(len(name) <= 64 and name.startswith("mcp__") for name in forward)

    # Residual or duplicate collision in used_names raises tool_namespace_collision instead of counter-renaming
    used_dup = {forward[0]}
    with pytest.raises(MCPLibraryError) as exc:
        namespace_mcp_tool_name("A", "echo", used_dup)
    assert exc.value.code == "tool_namespace_collision"


def test_mcp_tool_registry_preserves_open_object_schemas_and_literals_through_registration():
    open_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "payload": {"type": "object", "properties": {"nested": {"type": "object"}}},
            "literal_example": {
                "type": "object",
                "const": {"type": "object", "properties": {"keep_open": True}},
                "examples": [{"type": "object"}],
            },
        },
        "required": ["query"],
    }
    validated, _ = validate_mcp_input_schema(open_schema)
    name = namespace_mcp_tool_name("srv", "echo")
    tool = build_mcp_function_tool(
        {
            "server_id": "srv",
            "name": "echo",
            "namespaced_name": name,
            "description": "Echo open object",
            "input_schema": validated,
        },
        on_invoke=lambda _ctx, args: json.dumps(args),
    )

    registry = MCPToolRegistry()
    registry.register_executor(tool.to_executor())

    registered_params = registry.get_schema(name)["function"]["parameters"]
    assert "additionalProperties" not in registered_params
    assert "additionalProperties" not in registered_params["properties"]["payload"]
    assert "additionalProperties" not in registered_params["properties"]["payload"]["properties"]["nested"]
    assert registered_params["properties"]["literal_example"]["const"] == {
        "type": "object",
        "properties": {"keep_open": True},
    }
    assert registered_params["properties"]["literal_example"]["examples"] == [{"type": "object"}]

    listed_params = registry.list_openai_schemas(tool_names=[name])[0]["function"]["parameters"]
    assert "additionalProperties" not in listed_params

    # Executing through the registry accepts arbitrary extra keys on open objects
    call = ToolCall(
        id="call_1",
        name=name,
        arguments={
            "query": "ok",
            "extra_root": 123,
            "payload": {"extra_payload": "yes", "nested": {"deep_extra": [1, 2]}},
        },
    )
    exec_res = registry.execute(call, context=None)  # type: ignore[arg-type]
    assert exec_res.status_code.value.lower() == "success"
    assert validate_tool_arguments(registered_params, call.arguments) == []


def test_concurrent_overlapping_quiet_mcp_loggers_never_leak_secrets_or_corrupt_levels(caplog):
    original_call_handlers = logging.Logger.callHandlers
    original_handle = logging.Logger.handle
    app_logger = logging.getLogger("vectorvein.unrelated_app_test")
    orig_app_level = app_logger.level
    app_logger.setLevel(logging.INFO)
    child_mcp_logger = logging.getLogger("mcp.shared.review")
    orig_mcp_level = child_mcp_logger.level

    async def _run_overlapping():
        first = _quiet_mcp_loggers({"headers": {"Authorization": "Bearer synthetic-private-A"}})
        second = _quiet_mcp_loggers({"headers": {"Authorization": "Bearer synthetic-private-B"}})
        await first.__aenter__()
        await second.__aenter__()
        assert logging.Logger.callHandlers is original_call_handlers
        assert logging.Logger.handle is original_handle
        # Exit first while second is still active
        await first.__aexit__(None, None, None)
        child_mcp_logger.error("reply synthetic-private-B")
        app_logger.warning("app warning with synthetic-private-B")
        await second.__aexit__(None, None, None)

    try:
        with caplog.at_level(logging.DEBUG):
            anyio.run(_run_overlapping)
        assert "synthetic-private-A" not in caplog.text
        assert "synthetic-private-B" not in caplog.text
        assert child_mcp_logger.level == orig_mcp_level
        assert app_logger.level == logging.INFO
        assert logging.Logger.callHandlers is original_call_handlers
    finally:
        app_logger.setLevel(orig_app_level)


def test_ref_named_properties_and_literal_reference_data_remain_valid_schemas():
    schema = {
        "type": "object",
        "properties": {
            "$ref": {"type": "string"},
            "$schema": {"type": "string"},
            "payload": {
                "type": "object",
                "const": {"type": "object", "$ref": "https://example.invalid/literal"},
            },
        },
        "examples": [{"$ref": "https://example.invalid/example-data"}],
    }
    validated, _ = validate_mcp_input_schema(schema)
    assert validated == schema
    registry = MCPToolRegistry()
    tool = build_mcp_function_tool(
        {"server_id": "schema", "name": "echo", "namespaced_name": "mcp_schema_echo", "input_schema": schema},
        lambda *_: None,
    )
    registry.register_executor(tool.to_executor())
    assert registry.get_schema(tool.name)["function"]["parameters"] == schema


def test_error_contract_fixed_messages_and_pre_vs_post_dispatch_uncertainty():
    # Arbitrary remote exception message is replaced with fixed allowlisted message
    pre_proto = _classify_transport_error(RuntimeError("internal stack trace secret_xyz"), dispatched=False)
    assert pre_proto.code == "protocol_error"
    assert pre_proto.message == "MCP server returned a protocol or execution error"
    assert "secret_xyz" not in pre_proto.message
    assert pre_proto.dispatch_uncertain is False

    post_proto = _classify_transport_error(RuntimeError("internal stack trace"), dispatched=True)
    assert post_proto.code == "protocol_error"
    assert post_proto.dispatch_uncertain is True

    # HTTP 401 before dispatch vs after dispatch
    pre_auth = _classify_transport_error(RuntimeError("401"), dispatched=False, last_http_status=401)
    assert pre_auth.code == "authentication_failed"
    assert pre_auth.dispatch_uncertain is False

    post_auth = _classify_transport_error(RuntimeError("401"), dispatched=True, last_http_status=401)
    assert post_auth.code == "authentication_failed"
    assert post_auth.dispatch_uncertain is True

    # Oversized image is omitted and marks truncated=True without blowing up public JSON
    huge_b64 = base64.b64encode(b"x" * (6 * 1024 * 1024)).decode("ascii")
    raw_res = types.CallToolResult(
        content=[types.ImageContent(type="image", data=huge_b64, mime_type="image/png")]
    )
    formatted_pub = _format_call_tool_result(raw_res, include_internal_media=True)
    assert formatted_pub["truncated"] is True
    assert formatted_pub["content"][0]["retained"] is False
    assert formatted_pub["content"][0]["omitted"] is True
    assert formatted_pub["internal_media"] == []
