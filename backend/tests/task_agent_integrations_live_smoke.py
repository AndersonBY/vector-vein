"""Opt-in isolated real-model Skills/MCP acceptance; credentials remain external."""
import argparse
import ctypes
from ctypes import wintypes
import json
import logging
import os
from pathlib import Path
import sys
import time
import uuid


BACKEND_ROOT = Path(__file__).resolve().parents[1]

parser = argparse.ArgumentParser()
parser.add_argument("--settings", required=True)
parser.add_argument("--workspace", required=True)
args = parser.parse_args()
settings_file = Path(args.settings).resolve()
workspace = Path(args.workspace).resolve()
if workspace.exists() and any(workspace.iterdir()):
    raise ValueError("Use a new empty acceptance workspace")
workspace.mkdir(parents=True, exist_ok=True)
settings = json.loads(settings_file.read_text(encoding="utf-8-sig"))
model = "deepseek-v4.1-flash"
matches = [(backend, key) for backend, value in settings["backends"].items()
           for key, entry in value.get("models", {}).items()
           if key == model and entry.get("id", key) == model]
if len(matches) != 1:
    raise ValueError("Requested live model is not uniquely configured")
backend, selected_model = matches[0]
private_values = [entry.get("api_key") for entry in settings.get("endpoints", [])
                  if isinstance(entry.get("api_key"), str) and len(entry["api_key"]) >= 8]


class PrivateStream:
    def __init__(self, stream):
        self.stream = stream

    def write(self, value):
        for private in private_values:
            value = value.replace(private, "[REDACTED]")
        return self.stream.write(value)

    def flush(self):
        return self.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


sys.stdout, sys.stderr = PrivateStream(sys.stdout), PrivateStream(sys.stderr)
os.chdir(workspace)
os.environ["VECTORVEIN_LLM_SETTINGS_FILE"] = str(settings_file)
os.environ["VECTORVEIN_OUTPUT_DIR"] = str(workspace / "exports")
sys.path.insert(0, str(BACKEND_ROOT))
from cli import initialize  # noqa: E402 — settings and cwd must precede application imports.
from task_agent.service import TaskAgentService  # noqa: E402

initialize()
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.ERROR)
marker = "LIVE_REFERENCE_" + uuid.uuid4().hex[:14]
source = workspace / "synthetic_skill"
(source / "references").mkdir(parents=True)
(source / "references" / "check.txt").write_text(marker, encoding="utf-8")
(source / "SKILL.md").write_text(
    "---\nname: integration-check\ndescription: Verify native Skills and the selected synthetic MCP tools.\n---\n"
    "After activation read references/check.txt relative to this skill's SKILL.md directory. "
    "Use that exact marker in the selected stateful_step and peer_info tools. "
    "Never read credentials, environment variables or unrelated files. Do not run shell commands or write files.\n",
    encoding="utf-8",
)
call_log = workspace / "synthetic-mcp-calls.jsonl"
service = TaskAgentService(workspace)
report = {"model": model, "status": "pending", "approved_calls": 0}
pid = None
try:
    service.import_skill({"skill_id": "live_integration_skill", "path": str(source)})
    service.save_mcp_server({
        "server_id": "live_mcp", "name": "Synthetic local MCP acceptance", "transport": "stdio",
        "command": sys.executable,
        "args": [str(BACKEND_ROOT / "tests" / "mcp_test_server.py"), "runtime_stateful"],
        "env": {"FIXTURE_CALL_LOG": str(call_log)}, "timeout_seconds": 20,
    })
    discovered = service.test_mcp_server({"server_id": "live_mcp"})
    names = {tool["name"]: tool["namespaced_name"] for tool in discovered["tools"]}
    selected = [names["stateful_step"], names["peer_info"]]
    service.save_profile({"agent_id": "live_integrations", "name": "Live integration acceptance",
                          "instructions": "Follow the synthetic verification steps exactly and report only verified results.",
                          "max_cycles": 10, "permission_mode": "ask", "allow_shell": False,
                          "allow_file_writes": False, "allow_sub_agents": False,
                          "skill_ids": ["live_integration_skill"], "mcp_tool_ids": selected})
    goal = (
        "请完成一次真实接入验收：先用 activate_skill 激活 integration-check，按其指令读取 references/check.txt。"
        f"然后调用 {selected[0]}，tag 必须是文件中的完整标记，delay 为0；"
        f"再调用 {selected[1]}，note 也使用同一标记。两个调用必须顺序执行。"
        "最后用中文报告文件标记、两次调用返回的PID及计数，核实PID相同且计数递增。"
        "不要运行Bash、写文件、调用子代理或读取任何其他文件。权限批准由测试程序处理，不要询问用户。"
    )
    detail = service.create_task({"input_id": "live_skills_mcp", "turn_input_id": "start", "goal": goal,
                                  "agent_id": "live_integrations", "model_provider": backend, "model": selected_model})
    deadline = time.monotonic() + 240
    approved = set()
    while time.monotonic() < deadline:
        detail = service.get_task("live_skills_mcp")
        pending = detail.get("state", {}).get("pendingInteraction") or {}
        if pending.get("kind") == "approval" and pending["requestId"] not in approved:
            tool = pending.get("tool_name") or pending.get("toolName")
            approval = next((row for row in reversed(service.store.events("live_skills_mcp"))
                             if row.get("kind") == "approval_requested"
                             and row.get("request_id") == pending["requestId"]), {})
            planned = next((row for row in detail["timeline"]
                            if row.get("kind") == "tool" and row.get("turn_id") == pending["turnId"]
                            and row.get("tool_call_id") == approval.get("tool_call_id")), {})
            operation = pending.get("arguments") or planned.get("arguments") or {}
            allowed = (tool == selected[0] and operation.get("tag") == marker
                       and operation.get("delay", 0) == 0 and set(operation) <= {"tag", "delay"}) or (
                       tool == selected[1] and operation == {"note": marker})
            if not allowed:
                raise AssertionError("Unexpected approval request; nothing was authorized")
            service.approve({"task_id": "live_skills_mcp", "turn_id": detail["task"]["current_turn_id"],
                             "request_id": pending["requestId"], "decision": "allow"})
            approved.add(pending["requestId"])
            report["approved_calls"] += 1
        if detail["task"]["status"] in {"COMPLETED", "FAILED", "INTERRUPTED", "WAITING_FOR_USER"}:
            break
        time.sleep(0.3)
    report["status"] = detail["task"]["status"]
    assert report["status"] == "COMPLETED", report
    assert marker in detail["messages"][-1]["content"]
    tool_rows = [row for row in detail["timeline"] if row.get("kind") == "tool"]
    completed_tools = [row["tool_name"] for row in tool_rows if row.get("status") != "error"]
    assert all(tool in completed_tools for tool in ["activate_skill", "read_file", *selected]), completed_tools
    assert not {"bash", "write_file", "edit_file", "create_sub_task"}.intersection(completed_tools)
    assert report["approved_calls"] == 2
    call_lines = [line.split(":", 2) for line in call_log.read_text(encoding="utf-8").splitlines() if line]
    assert len(call_lines) == 1 and call_lines[0][1:] == ["1", marker], len(call_lines)
    jobs = service.store.mcp_jobs("live_skills_mcp")
    assert len(jobs) == 2 and all(job["status"] == "FINISHED" for job in jobs)
    returns = [json.loads(job["result"]["content"])["structured_content"] for job in jobs]
    assert [value["call_count"] for value in returns] == [1, 2]
    pids = [value["pid"] for value in returns]
    assert len(set(pids)) == 1
    pid = pids[0]
    assert int(call_lines[0][0]) == pid
    assert all(row["status"] == "FINISHED" for row in detail["mcp_runs"])
    public = json.dumps(detail, ensure_ascii=False)
    assert all(private not in public for private in private_values)
    report.update(native_skill=True, bundled_resource=True, stateful_mcp=True, same_pid=True,
                  mcp_calls=len(jobs), credentials_absent=True,
                  recovered_tool_errors=[row.get("error_code") for row in tool_rows if row.get("status") == "error"])
finally:
    service.stop()
for database in (service.task_root / "tasks.db", service.task_root / "sessions.db"):
    for stored_file in (database, database.with_name(database.name + "-wal")):
        try:
            stored_bytes = stored_file.read_bytes()
        except FileNotFoundError:
            continue
        assert all(private.encode() not in stored_bytes for private in private_values)
if os.name == "nt" and pid:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000 | 0x100000, False, pid)
    if handle:
        try:
            assert kernel.WaitForSingleObject(handle, 1000) == 0, "Owned MCP process still active"
        finally:
            kernel.CloseHandle(handle)
    report["owned_process_exited"] = True
(workspace / "acceptance-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False))
