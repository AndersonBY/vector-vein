"""Small product projections of public App Server RunEvent v6 values."""
from __future__ import annotations

from datetime import datetime, timezone
import json


def event_time(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if isinstance(value, (int, float)) else value


def project_event(event: dict) -> dict | None:
    kind = event["type"]
    common = {
        "id": event["event_id"], "turn_id": event["run_id"], "kind": kind,
        "created_at": event_time(event["created_at"]), "cycle": event.get("cycle_index"),
    }
    if kind == "diagnostic" and event.get("code") == "cycle_llm_response":
        text = event.get("details", {}).get("assistant_message", "")
        return {**common, "kind": "assistant", "text": text} if text else None
    if kind in {"tool_call_planned", "tool_call_started", "tool_call_completed"}:
        data = {key: event.get(key) for key in (
            "tool_name", "tool_call_id", "arguments", "status", "duration_ms", "error_code",
        ) if key in event}
        if kind == "tool_call_completed":
            data["result"] = event.get("metadata", {}).get("tool_result")
            data["result_event_id"] = event["event_id"]
        return {**common, **data}
    if kind in {"sub_run_started", "sub_run_completed"}:
        return {**common, **{key: event.get(key) for key in (
            "parent_tool_call_id", "child_session_id", "status", "final_output", "error",
        )}}
    if kind in {"model_call_failed", "model_call_completed"}:
        from .usage import clean_usage
        return {**common, "kind": "model_failure" if kind == "model_call_failed" else "model_success",
                "call_id": event["call_id"], "operation_id": event["operation_id"], "attempt": event.get("attempt", 1),
                "operation": event.get("operation"), "usage": clean_usage(event.get("usage")),
                "error_code": event.get("error_code"), "outcome": event.get("outcome")}
    if kind == "run_completed":
        return {**common, "kind": "final", "text": event.get("final_output"), "status": event.get("status")}
    if kind == "run_failed":
        return {**common, "kind": "error", "text": event.get("error", ""), "status": "failed"}
    if kind == "host_interaction_requested":
        return {**common, "kind": "question", "text": event.get("prompt", "")}
    if kind in {"approval_requested", "approval_resolved"}:
        return {**common, **{key: event.get(key) for key in ("request_id", "tool_name", "tool_call_id", "message", "action")},
                "arguments": event.get("metadata", {}).get("arguments", {})}
    if kind in {"memory_compact_started", "memory_compact_completed"}:
        import re
        metadata = event.get("metadata") or {}
        return {**common, "compaction_requests": [value for value in metadata.get("requested_by", []) if isinstance(value, str) and re.fullmatch(r"compaction/[0-9a-f]{64}", value)][:16],
                "compaction_failed": bool(metadata.get("compaction_error"))}
    if kind == "diagnostic" and event.get("code") == "context_compaction_failed":
        import re
        return {**common, "kind": "context_compaction_failed", "compaction_failed": True,
                "compaction_requests": [value for value in (event.get("details") or {}).get("request_ids", []) if isinstance(value, str) and re.fullmatch(r"compaction/[0-9a-f]{64}", value)][:16]}
    if kind == "run_cancelled":
        return common
    return None


def build_timeline(events: list[dict]) -> tuple[list[dict], list[dict]]:
    timeline = []
    tools = {}
    todos = []
    children = {}
    last_assistant = {}
    for event in events:
        kind = event["kind"]
        turn = event["turn_id"]
        if kind in {"sub_run_started", "sub_run_completed"}:
            key = (turn, event["child_session_id"])
            if key not in children:
                children[key] = {**event, "kind": "sub_agent"}
                timeline.append(children[key])
            children[key].update({k: v for k, v in event.items() if k not in {"id", "created_at", "kind"}})
        elif kind.startswith("tool_call_"):
            key = (turn, event["tool_call_id"])
            if key not in tools:
                tools[key] = {**event, "kind": "tool", "status": "pending"}
                timeline.append(tools[key])
            tool = tools[key]
            tool.update({k: v for k, v in event.items() if k not in {"id", "created_at", "kind"}})
            if kind == "tool_call_started":
                tool["status"] = "running"
            if kind == "tool_call_completed" and event.get("status") == "success" and event["tool_name"] == "todo_write":
                todos = tool.get("arguments", {}).get("todos", [])
        elif kind in {"assistant", "final"}:
            text = event.get("text")
            if text is None or text == "":
                continue
            if kind == "final" and last_assistant.get(turn, {}).get("text") == text:
                last_assistant[turn]["final"] = True
                continue
            response = {**event, "kind": "assistant", "final": kind == "final"}
            timeline.append(response)
            last_assistant[turn] = response
        elif kind not in {"model_failure", "model_success"}:
            timeline.append(event)
    command_states = {}
    command_tools = []
    for tool in tools.values():
        if tool.get("tool_name") not in {"bash", "check_background_command", "stop_background_command"}:
            continue
        result = tool.get("result") or {}
        if result.get("truncated"):
            continue
        try:
            payload = json.loads(result.get("preview", ""))
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        session = payload.get("session_id") or (tool.get("arguments") or {}).get("session_id")
        status = payload.get("status")
        if isinstance(session, str) and status in {"running", "stopping", "unknown", "completed", "failed", "timeout", "stopped"}:
            key = (tool["turn_id"], session)
            command_states[key] = status
            command_tools.append((key, tool))
    ended_turns = {event["turn_id"] for event in events if event["kind"] in {"final", "error", "run_cancelled"}}
    for key, tool in command_tools:
        tool["command_status"] = command_states[key]
        if key[0] in ended_turns and tool["command_status"] in {"running", "stopping"}:
            tool["command_status"] = "unknown"
            tool["command_status_reason"] = "turn_ended_without_terminal_observation"
    return timeline, todos
