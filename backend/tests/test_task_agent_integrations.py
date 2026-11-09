from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import threading
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from api import task_agent_api
from task_agent.host import DesktopTaskAgentHost, desktop_tool_registry
from task_agent.mcp_library import build_mcp_function_tool, namespace_mcp_tool_name
from task_agent.permissions import requires_approval
from task_agent.service import TaskAgentService, TaskConflict


class FakeProcess:
    def __init__(self):
        self.requests = []
        self.started = 0

    def start(self):
        self.started += 1
        return {"pid": 12345}

    def stop(self):
        pass

    def request(self, method, params):
        self.requests.append((method, deepcopy(params)))
        if method == "thread/start":
            return {"threadId": params["inputId"]}
        if method == "turn/start":
            return {"turnId": f"{params['threadId']}/turn/{params['inputId']}"}
        if method in {"thread/read", "thread/resume"}:
            return {"state": {"status": "idle"}, "turns": []}
        if method == "thread/events/list":
            return {"events": [], "more": False, "nextCursor": None, "throughCursor": None}
        return {}


@pytest.fixture
def service_and_api(tmp_path, monkeypatch):
    proc = FakeProcess()
    service = TaskAgentService(tmp_path / "workspace", process=proc, data_path=tmp_path / "data")
    llm = {
        "VERSION": "2",
        "endpoints": [
            {
                "id": "configured",
                "api_base": "https://example.invalid/v1",
                "api_key": "synthetic-llm-private-key",
            }
        ],
        "backends": {
            "local": {
                "models": {
                    "enabled": {
                        "id": "wire-model",
                        "endpoints": ["configured"],
                        "enabled": True,
                        "function_call_available": True,
                        "capabilities": {"reasoning_efforts": ["low"]},
                    }
                }
            }
        },
    }
    monkeypatch.setattr("task_agent.service.current_llm_settings", lambda: deepcopy(llm))
    monkeypatch.setattr("task_agent.workflows.selected_workflows", lambda values: [])
    monkeypatch.setattr(task_agent_api, "task_agent_service", lambda: service)
    api = task_agent_api.TaskAgentAPI()
    yield service, api, proc
    service.stop()


def _skill_md(name: str, description: str = "Skill description", body: str = "Follow instructions.") -> str:
    return f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n"


def test_skills_api_crud_import_and_versioned_resources_after_catalog_delete(service_and_api, tmp_path):
    service, api, proc = service_and_api

    # Create v1 via save_skill
    res1 = api.save_skill({
        "skill_id": "alpha_skill",
        "content": _skill_md("alpha-skill", "Alpha v1", "Version 1 instructions"),
    })
    assert res1["status"] == 200
    assert res1["data"]["version"] == 1
    v1_updated = res1["data"]["updated_at"]

    # Import v2 from a directory with bundled reference
    src_dir = tmp_path / "import_src"
    (src_dir / "references").mkdir(parents=True)
    (src_dir / "SKILL.md").write_text(
        _skill_md("alpha-skill", "Alpha v2", "Version 2 instructions"),
        encoding="utf-8",
    )
    (src_dir / "references" / "guide.md").write_text("Reference v2 content", encoding="utf-8")

    res2 = api.import_skill({
        "skill_id": "alpha_skill",
        "path": str(src_dir),
        "expected_updated_at": v1_updated,
    })
    assert res2["status"] == 200
    assert res2["data"]["version"] == 2

    # List and detail
    listed = api.skills({"search": "alpha"})
    assert listed["status"] == 200
    assert [item["skill_id"] for item in listed["data"]["skills"]] == ["alpha_skill"]
    detail = api.skill({"skill_id": "alpha_skill"})
    assert detail["status"] == 200
    assert detail["data"]["version"] == 2

    # Delete catalog entry; versioned files and preview for both v1 and v2 must still work
    deleted = api.delete_skill({"skill_id": "alpha_skill", "expected_updated_at": res2["data"]["updated_at"]})
    assert deleted["status"] == 200
    assert deleted["data"]["deleted"] is True
    assert api.skill({"skill_id": "alpha_skill"})["status"] == 404

    v1_files = api.skill_files({"skill_id": "alpha_skill", "version": 1})
    assert v1_files["status"] == 200
    assert v1_files["data"]["version"] == 1
    v1_preview = api.skill_preview_file({"skill_id": "alpha_skill", "path": "SKILL.md", "version": 1})
    assert v1_preview["status"] == 200
    assert "Version 1 instructions" in v1_preview["data"]["text"]

    v2_files = api.skill_files({"skill_id": "alpha_skill", "version": 2})
    assert v2_files["status"] == 200
    assert any(f["relative_path"] == "references/guide.md" for f in v2_files["data"]["files"])
    v2_preview = api.skill_preview_file({"skill_id": "alpha_skill", "path": "references/guide.md", "version": 2})
    assert v2_preview["status"] == 200
    assert v2_preview["data"]["text"] == "Reference v2 content"

    # Management calls never started AppServerProcess
    assert proc.started == 0


def test_mcp_api_crud_test_tool_toggle_and_no_connections_on_list_get(service_and_api, monkeypatch):
    service, api, proc = service_and_api
    server_script = Path(__file__).with_name("mcp_test_server.py").resolve()

    saved = api.save_mcp_server({
        "server_id": "local_stdio",
        "name": "Local Stdio Server",
        "description": "Test stdio MCP",
        "transport": "stdio",
        "command": sys.executable,
        "args": [str(server_script), "paginated"],
        "env": {"SYNTHETIC_STDIO_SECRET": "synthetic-mcp-secret-999"},
    })
    assert saved["status"] == 200
    assert "synthetic-mcp-secret-999" not in json.dumps(saved)
    assert saved["data"]["env_keys"] == ["SYNTHETIC_STDIO_SECRET"]
    assert saved["data"]["has_env"] is True

    # Forbid open_mcp_client during list/get/mcp_tools
    import task_agent.mcp_library as mcp_lib
    real_open = mcp_lib.open_mcp_client
    monkeypatch.setattr(
        mcp_lib,
        "open_mcp_client",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("Must not connect on list/get")),
    )
    assert api.mcp_servers({})["status"] == 200
    assert api.mcp_server({"server_id": "local_stdio"})["status"] == 200
    assert api.mcp_tools({})["data"]["tools"] == []
    monkeypatch.setattr(mcp_lib, "open_mcp_client", real_open)

    # Explicit test_mcp_server connects and discovers tools
    tested = api.test_mcp_server({"server_id": "local_stdio"})
    assert tested["status"] == 200
    assert tested["data"]["last_test_status"] == "ok"
    tools = tested["data"]["tools"]
    assert len(tools) >= 2
    echo_tool = next(t for t in tools if t["name"] == "echo_env")
    ns_echo = echo_tool["namespaced_name"]

    # Flattened catalog returns enabled tools with server labels
    catalog = api.mcp_tools({})
    assert catalog["status"] == 200
    assert any(t["namespaced_name"] == ns_echo and t["server_name"] == "Local Stdio Server" for t in catalog["data"]["tools"])
    assert "synthetic-mcp-secret-999" not in json.dumps(catalog)

    # Toggle one tool off; it disappears from mcp_tools selection catalog
    toggled = api.set_mcp_tool_enabled({
        "server_id": "local_stdio",
        "tool_name": "echo_env",
        "enabled": False,
    })
    assert toggled["status"] == 200
    catalog_after = api.mcp_tools({})
    assert all(t["namespaced_name"] != ns_echo for t in catalog_after["data"]["tools"])

    # Generic sqlite error on non-deletion API does not include misleading deletion_error
    monkeypatch.setattr(service, "list_skills", lambda search="": (_ for _ in ()).throw(sqlite3.OperationalError("locked")))
    err_resp = api.skills({})
    assert err_resp["status"] == 503
    assert "deletion_error" not in (err_resp.get("data") or {})
    assert proc.started == 0


def test_profile_selection_validation_duplicate_skill_names_and_stale_mcp_rejection(service_and_api):
    service, api, _ = service_and_api

    # Create two distinct skill_ids with the SAME internal frontmatter name
    api.save_skill({"skill_id": "skill_one", "content": _skill_md("shared-name", "First copy")})
    api.save_skill({"skill_id": "skill_two", "content": _skill_md("shared-name", "Second copy")})
    api.save_skill({"skill_id": "skill_disabled", "content": _skill_md("disabled-skill", "Disabled"), "enabled": False})

    base_profile = {
        "agent_id": "custom_agent",
        "name": "Custom Agent",
        "description": "Tests integrations",
        "instructions": "Follow instructions.",
        "max_cycles": 10,
        "allow_file_writes": False,
        "allow_shell": False,
        "allow_sub_agents": True,
        "permission_mode": "ask",
    }

    # Duplicate internal skill name rejected
    dup_resp = api.save_profile({**base_profile, "skill_ids": ["skill_one", "skill_two"]})
    assert dup_resp["status"] == 400
    assert dup_resp["data"]["integration_error"]["kind"] == "skills"
    assert dup_resp["data"]["integration_error"]["code"] == "duplicate_skill_name"

    # Disabled skill rejected
    dis_resp = api.save_profile({**base_profile, "skill_ids": ["skill_disabled"]})
    assert dis_resp["status"] == 400
    assert dis_resp["data"]["integration_error"]["code"] == "skill_disabled"

    # Missing skill rejected
    miss_resp = api.save_profile({**base_profile, "skill_ids": ["nonexistent_skill"]})
    assert miss_resp["status"] == 400
    assert miss_resp["data"]["integration_error"]["code"] == "skill_not_found"

    # Save valid MCP server + test
    server_script = Path(__file__).with_name("mcp_test_server.py").resolve()
    api.save_mcp_server({
        "server_id": "srv_a",
        "name": "Server A",
        "transport": "stdio",
        "command": sys.executable,
        "args": [str(server_script), "paginated"],
    })
    tested = api.test_mcp_server({"server_id": "srv_a"})["data"]
    ns_echo = next(t["namespaced_name"] for t in tested["tools"] if t["name"] == "echo_env")

    # Valid profile save with skill_one + ns_echo
    ok_resp = api.save_profile({
        **base_profile,
        "skill_ids": ["skill_one"],
        "mcp_tool_ids": [ns_echo],
    })
    assert ok_resp["status"] == 200
    assert ok_resp["data"]["skill_ids"] == ["skill_one"]
    assert ok_resp["data"]["mcp_tool_ids"] == [ns_echo]

    # Modify server connection config so discovery becomes stale -> profile save with stale tool rejected
    api.save_mcp_server({
        "server_id": "srv_a",
        "name": "Server A",
        "transport": "stdio",
        "command": sys.executable,
        "args": [str(server_script), "paginated", "--extra-arg"],
    })
    stale_resp = api.save_profile({
        **base_profile,
        "skill_ids": ["skill_one"],
        "mcp_tool_ids": [ns_echo],
    })
    assert stale_resp["status"] == 400
    assert stale_resp["data"]["integration_error"]["kind"] == "mcp"
    assert stale_resp["data"]["integration_error"]["code"] == "discovery_stale"


def test_task_freezing_per_task_overrides_idempotent_retries_and_compact_views(service_and_api):
    service, api, _ = service_and_api
    server_script = Path(__file__).with_name("mcp_test_server.py").resolve()

    api.save_skill({
        "skill_id": "freeze_skill",
        "content": _skill_md("freeze-skill", "Frozen v1", "Frozen instructions v1"),
    })
    api.save_mcp_server({
        "server_id": "freeze_srv",
        "name": "Freeze Server",
        "transport": "stdio",
        "command": sys.executable,
        "args": [str(server_script), "paginated"],
        "env": {"SYNTHETIC_STDIO_SECRET": "never-in-task-snapshot-xyz"},
    })
    tested = api.test_mcp_server({"server_id": "freeze_srv"})["data"]
    ns_echo = next(t["namespaced_name"] for t in tested["tools"] if t["name"] == "echo_env")
    ns_slow = next(t["namespaced_name"] for t in tested["tools"] if t["name"] == "slow_op")

    api.save_profile({
        "agent_id": "frozen_agent",
        "name": "Frozen Agent",
        "description": "",
        "instructions": "Use frozen capabilities.",
        "max_cycles": 10,
        "allow_file_writes": True,
        "allow_shell": False,
        "allow_sub_agents": False,
        "permission_mode": "auto",
        "skill_ids": ["freeze_skill"],
        "mcp_tool_ids": [ns_echo],
    })

    # 1. Task creation with profile defaults
    created = service.create_task({
        "input_id": "task_default_caps",
        "goal": "Run with default profile capabilities",
        "agent_id": "frozen_agent",
        "model_provider": "Local",
        "model": "enabled",
        "reasoning_effort": "low",
    })
    public_snap = created["task"]["config_snapshot"]
    assert [s["skill_id"] for s in public_snap["skills"]] == ["freeze_skill"]
    assert public_snap["skills"][0]["version"] == 1
    assert "location" not in public_snap["skills"][0]  # compact public view omits filesystem paths
    assert [t["namespaced_name"] for t in public_snap["mcp_tools"]] == [ns_echo]
    assert "input_schema" not in public_snap["mcp_tools"][0]  # compact public view omits bulky input_schema

    # Stored DB snapshot retains location, bundle_path, input_schema, connection_fingerprint, and NEVER secrets
    raw_task = service.store.get_task("task_default_caps")
    raw_snap = raw_task["config_snapshot"]
    assert Path(raw_snap["skills"][0]["location"]).is_file()
    assert "input_schema" in raw_snap["mcp_tools"][0]
    assert raw_snap["mcp_tools"][0]["connection_fingerprint"]
    assert "never-in-task-snapshot-xyz" not in json.dumps(raw_snap)
    assert "synthetic-llm-private-key" not in json.dumps(raw_snap)

    # 2. Upgrade skill to v2 and change profile defaults; idempotent retry of task_default_caps keeps v1 & ns_echo
    api.save_skill({
        "skill_id": "freeze_skill",
        "content": _skill_md("freeze-skill", "Frozen v2", "Frozen instructions v2"),
    })
    api.save_profile({
        "agent_id": "frozen_agent",
        "name": "Frozen Agent",
        "description": "",
        "instructions": "Use frozen capabilities.",
        "max_cycles": 10,
        "allow_file_writes": True,
        "allow_shell": False,
        "allow_sub_agents": False,
        "permission_mode": "auto",
        "skill_ids": ["freeze_skill"],
        "mcp_tool_ids": [ns_slow],
    })

    retried = service.create_task({
        "input_id": "task_default_caps",
        "goal": "Run with default profile capabilities",
        "agent_id": "frozen_agent",
        "model_provider": "Local",
        "model": "enabled",
        "reasoning_effort": "low",
    })
    assert retried["task"]["config_snapshot"]["skills"][0]["version"] == 1
    assert [t["namespaced_name"] for t in retried["task"]["config_snapshot"]["mcp_tools"]] == [ns_echo]

    # Conflicting mcp_tool_ids on same input_id raises TaskConflict
    with pytest.raises(TaskConflict, match="different MCP tool selections"):
        service.create_task({
            "input_id": "task_default_caps",
            "goal": "Run with default profile capabilities",
            "agent_id": "frozen_agent",
            "model_provider": "Local",
            "model": "enabled",
            "reasoning_effort": "low",
            "mcp_tool_ids": [],
        })

    # 3. Per-task explicit empty override [] clears MCP tools without mutating profile
    cleared = service.create_task({
        "input_id": "task_cleared_mcp",
        "goal": "Run with no MCP tools",
        "agent_id": "frozen_agent",
        "model_provider": "Local",
        "model": "enabled",
        "reasoning_effort": "low",
        "mcp_tool_ids": [],
    })
    assert cleared["task"]["config_snapshot"]["mcp_tools"] == []
    assert service.get_profile("frozen_agent")["mcp_tool_ids"] == [ns_slow]
    # retry_start preserves the explicit [] override
    restarted_clear = service.retry_start("task_cleared_mcp")
    assert restarted_clear["task"]["config_snapshot"]["mcp_tools"] == []


def test_host_validates_frozen_integrations_and_preserves_mcp_open_schema_and_skill_read_permissions(service_and_api, tmp_path):
    service, api, _ = service_and_api
    api.save_skill({
        "skill_id": "host_skill",
        "content": _skill_md("host-skill", "Host skill", "Use reference."),
    })
    api.save_profile({
        "agent_id": "host_agent",
        "name": "Host Agent",
        "description": "",
        "instructions": "Base instructions.",
        "max_cycles": 10,
        "allow_file_writes": False,
        "allow_shell": False,
        "allow_sub_agents": True,
        "permission_mode": "ask",
        "skill_ids": ["host_skill"],
    })
    service.create_task({
        "input_id": "task_host",
        "goal": "Test host",
        "agent_id": "host_agent",
        "model_provider": "Local",
        "model": "enabled",
        "reasoning_effort": "low",
    })
    saved_task = service.store.get_task("task_host")
    snapshot = deepcopy(saved_task["config_snapshot"])
    cwd = str(service._task_workspace("task_host"))
    host = DesktopTaskAgentHost(
        service.task_root,
        settings_loader=lambda: {
            "VERSION": "2",
            "endpoints": [{"id": "configured", "api_base": "https://example.invalid/v1", "api_key": "k"}],
            "backends": {"local": {"models": {"enabled": {"id": "wire-model", "endpoints": ["configured"], "enabled": True}}}},
        },
    )

    assert host.authorize("conn", "thread/start", {
        "agentKey": "desktop-task",
        "inputId": "task_host",
        "cwd": cwd,
        "metadata": {"model_snapshot": snapshot},
    }) is True

    # Forged skill location is rejected by authorize and build_run_config
    forged = deepcopy(snapshot)
    forged["skills"][0]["location"] = str(tmp_path / "outside" / "SKILL.md")
    assert host.authorize("conn", "thread/start", {
        "agentKey": "desktop-task",
        "inputId": "task_host",
        "cwd": cwd,
        "metadata": {"model_snapshot": forged},
    }) is False

    req = SimpleNamespace(thread_id="task_host", cwd=cwd, metadata={"model_snapshot": snapshot})
    agent = host.resolve_agent(req)
    assert "<available_skills>" in agent.instructions
    assert "host-skill" in agent.instructions
    assert "<available_skills>" in agent.sub_agents["worker"].system_prompt

    run_cfg = host.build_run_config(req)
    assert "activate_skill" in run_cfg.tool_policy.allowed_tools
    assert "write_file" not in run_cfg.tool_policy.allowed_tools
    assert "bash" not in run_cfg.tool_policy.allowed_tools

    # Read-only tools inside pinned skill_roots do not require approval even in 'ask' mode, while writes do
    skill_root = run_cfg.metadata["skill_roots"][0]
    skill_md_file = str(Path(skill_root) / "SKILL.md")
    outside_file = str(tmp_path / "outside.txt")
    ctx = SimpleNamespace(workspace=Path(cwd), task_metadata=run_cfg.metadata, ctx=None)
    assert requires_approval("ask", "read_file", ctx, {"path": skill_md_file}) is False
    assert requires_approval("ask", "write_file", ctx, {"path": skill_md_file}) is True
    assert requires_approval("ask", "read_file", ctx, {"path": outside_file}) is True

    # desktop_tool_registry returns MCPToolRegistry preserving open JSON schemas for MCP tools
    reg = desktop_tool_registry("ask")
    mcp_tool = build_mcp_function_tool(
        {
            "server_id": "srv",
            "name": "open_echo",
            "namespaced_name": namespace_mcp_tool_name("srv", "open_echo"),
            "input_schema": {
                "type": "object",
                "properties": {"payload": {"type": "object"}},
            },
        },
        lambda _ctx, _args: None,
    )
    reg.register_executor(mcp_tool.to_executor())
    compiled_schema = reg.get_schema(mcp_tool.name)["function"]["parameters"]
    assert "additionalProperties" not in compiled_schema
    assert "additionalProperties" not in compiled_schema["properties"]["payload"]


class DeterministicSkillModelHandler(BaseHTTPRequestHandler):
    requests = []

    def _send_sse(self, model: str, delta: dict, finish_reason: str):
        chunks = [
            {
                "id": "mock",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
            },
            {
                "id": "mock",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
            },
        ]
        body = ("".join(f"data: {json.dumps(c, ensure_ascii=False)}\n\n" for c in chunks) + "data: [DONE]\n\n").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).requests.append(payload)
        messages = payload.get("messages", [])
        sys_text = "\n".join(m.get("content", "") for m in messages if m.get("role") == "system" and isinstance(m.get("content"), str))
        tool_names = {t["function"]["name"] for t in payload.get("tools", []) if "function" in t}

        # Verify unselected skill never appears in system prompt, and bash/write_file are not re-enabled by skill frontmatter
        assert "unselected-secret-skill" not in sys_text
        assert "domain-guide" in sys_text
        assert "activate_skill" in tool_names
        assert "bash" not in tool_names
        assert "write_file" not in tool_names

        is_child = "Complete only the delegated task." in sys_text
        tool_messages = [m for m in messages if m.get("role") == "tool"]
        user_messages = [m for m in messages if m.get("role") == "user"]
        last_user = user_messages[-1]["content"] if user_messages else ""

        if is_child:
            # Child sub-agent activates domain-guide and confirms it has access to the selected skill
            if not tool_messages:
                self._send_sse(
                    payload["model"],
                    {
                        "role": "assistant",
                        "content": "Child activating skill",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "child-act-1",
                                "type": "function",
                                "function": {
                                    "name": "activate_skill",
                                    "arguments": json.dumps({"skill_name": "domain-guide", "reason": "worker check"}),
                                },
                            }
                        ],
                    },
                    "tool_calls",
                )
                return
            last_tool_data = json.loads(tool_messages[-1]["content"])
            assert "SYNTHETIC_SKILL_MARKER_V1" in last_tool_data.get("instructions", "")
            self._send_sse(
                payload["model"],
                {"role": "assistant", "content": "WORKER_VERIFIED_V1"},
                "stop",
            )
            return

        # Follow-up turn after restart and catalog deletion
        if "Re-activate domain-guide after restart" in last_user:
            # Check if activate_skill was already called in this turn (last message is role=="tool")
            if messages[-1].get("role") != "tool":
                self._send_sse(
                    payload["model"],
                    {
                        "role": "assistant",
                        "content": "Re-activating pinned skill",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "parent-act-followup",
                                "type": "function",
                                "function": {
                                    "name": "activate_skill",
                                    "arguments": json.dumps({"skill_name": "domain-guide", "reason": "followup check"}),
                                },
                            }
                        ],
                    },
                    "tool_calls",
                )
                return
            act_data = json.loads(messages[-1]["content"])
            assert "SYNTHETIC_SKILL_MARKER_V1" in act_data["instructions"]
            self._send_sse(
                payload["model"],
                {"role": "assistant", "content": "FOLLOWUP_CONFIRMED_V1:SYNTHETIC_SKILL_MARKER_V1"},
                "stop",
            )
            return

        # First turn of parent:
        # Step 0: call activate_skill
        if len(tool_messages) == 0:
            self._send_sse(
                payload["model"],
                {
                    "role": "assistant",
                    "content": "Activating domain-guide skill.",
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "parent-act-1",
                            "type": "function",
                            "function": {
                                "name": "activate_skill",
                                "arguments": json.dumps({"skill_name": "domain-guide", "reason": "load instructions"}),
                            },
                        }
                    ],
                },
                "tool_calls",
            )
            return

        # Step 1: read bundled reference file from the activated skill's pinned directory
        if len(tool_messages) == 1:
            act_data = json.loads(tool_messages[0]["content"])
            assert act_data["status"] == "activated"
            assert "SYNTHETIC_SKILL_MARKER_V1" in act_data["instructions"]
            skill_md_loc = Path(act_data["location"])
            ref_path = str(skill_md_loc.parent / "references" / "spec.txt")
            self._send_sse(
                payload["model"],
                {
                    "role": "assistant",
                    "content": "Reading bundled reference.",
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "parent-read-ref-1",
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": json.dumps({"path": ref_path}),
                            },
                        }
                    ],
                },
                "tool_calls",
            )
            return

        # Step 2: delegate to worker child agent
        if len(tool_messages) == 2:
            ref_content = tool_messages[1]["content"]
            assert "BUNDLED_REF_VALUE_V1_4242" in ref_content
            self._send_sse(
                payload["model"],
                {
                    "role": "assistant",
                    "content": "Delegating verification to worker.",
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "parent-sub-1",
                            "type": "function",
                            "function": {
                                "name": "create_sub_task",
                                "arguments": json.dumps({
                                    "agent_id": "worker",
                                    "task_description": "Activate domain-guide and confirm v1 marker.",
                                    "wait_for_completion": True,
                                }),
                            },
                        }
                    ],
                },
                "tool_calls",
            )
            return

        # Step 3: finish with combined output
        sub_content = tool_messages[2]["content"]
        self._send_sse(
            payload["model"],
            {
                "role": "assistant",
                "content": f"Completed: BUNDLED_REF_VALUE_V1_4242 | {sub_content}",
            },
            "stop",
        )

    def log_message(self, *args):
        pass


def test_real_appserver_skills_activation_reference_read_pinned_revision_and_worker_scope(tmp_path):
    DeterministicSkillModelHandler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), DeterministicSkillModelHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    script = Path(__file__).with_name("task_agent_skills_smoke.py")
    try:
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(script), str(tmp_path), str(server.server_port)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        assert json.loads(result.stdout) == {"status": "COMPLETED", "turns": 2}
        assert len(DeterministicSkillModelHandler.requests) >= 6
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)