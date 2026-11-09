"""MCP privacy checks must preserve unrelated native-tool risk review."""
import json
import sys

from vv_agent.approval import ApprovalRequest

from task_agent.mcp_library import MCPLibrary
from task_agent.risk_review import LLMApprovalProvider
from task_agent.store import BusinessStore, now


SETTINGS = {"task_agent_approval": {"model_provider": "fixture", "model": "reviewer"},
            "llm_settings": {"endpoints": []}}
SAFE = {"decision": "allow", "risk": "low", "reason": "within_scope"}


def review_store(tmp_path, *, selected=False, env=None):
    store = BusinessStore(tmp_path / "tasks.db")
    library = MCPLibrary(tmp_path, store=store)
    library.save({"server_id": "risk_server", "name": "Risk fixture", "transport": "stdio",
                  "command": sys.executable, "args": [], "env": env or {}})
    descriptor = {"server_id": "risk_server", "server_name": "Risk fixture", "transport": "stdio",
                  "name": "inspect", "namespaced_name": "mcp_review_inspect", "description": "Synthetic inspection",
                  "annotations": {"readOnlyHint": True}, "input_schema": {"type": "object"}}
    timestamp = now()
    store.create_task({"tid": "task", "thread_id": "task", "title": "Report", "goal": "Create outputs/report.txt",
                       "status": "PROCESSING", "current_turn_id": "task/turn/one", "model_provider": "fixture",
                       "model": "primary", "reasoning_effort": "default",
                       "config_snapshot": {"mcp_tools": [descriptor] if selected else []},
                       "created_at": timestamp, "updated_at": timestamp})
    return store, descriptor


def approval(tool="write_file", **arguments):
    return ApprovalRequest(request_id="review-one", tool_name=tool, tool_call_id="call-one",
                           run_id="task/turn/one", arguments=arguments or {"path": "outputs/report.txt", "content": "Report"})


def test_unselected_noncredential_mcp_environment_does_not_disable_native_review(tmp_path):
    store, _ = review_store(tmp_path, env={"MODE": "workspace"})
    calls = []
    reviewer = LLMApprovalProvider(store, "task", settings_loader=lambda: SETTINGS,
                                   evaluate=lambda *args: (calls.append(json.loads(args[-1])) or SAFE))
    decision = reviewer.decide(approval())
    assert decision is not None and decision.action == "allow"
    assert len(calls) == 1


def test_selected_mcp_credentials_are_not_sent_to_reviewer_for_other_tools(tmp_path):
    secret = "SYNTHETIC_MCP_REVIEW_SECRET_VALUE"
    store, _ = review_store(tmp_path, selected=True, env={"API_KEY": secret})
    calls = []
    reviewer = LLMApprovalProvider(store, "task", settings_loader=lambda: SETTINGS,
                                   evaluate=lambda *args: (calls.append(1) or SAFE))
    assert reviewer.decide(approval(content=secret)) is None
    assert calls == []
    retained = store.risk_reviews("task")
    assert retained[0]["reason"] == "credentials"
    assert secret not in json.dumps(retained)


def test_readonly_annotation_still_uses_independent_review_and_safe_tool_evidence(tmp_path):
    secret = "SYNTHETIC_MCP_REVIEW_SECRET_VALUE"
    store, descriptor = review_store(tmp_path, selected=True, env={"API_KEY": secret})
    evidence = []
    reviewer = LLMApprovalProvider(store, "task", settings_loader=lambda: SETTINGS,
                                   evaluate=lambda *args: (evidence.append(json.loads(args[-1])) or SAFE))
    decision = reviewer.decide(approval(descriptor["namespaced_name"], value="synthetic"))
    assert decision is not None and decision.action == "allow"
    assert len(evidence) == 1
    assert evidence[0]["mcp_tool"]["server_id"] == descriptor["server_id"]
    assert evidence[0]["mcp_tool"]["untrusted_server_metadata"] is True
    assert secret not in json.dumps(evidence)
