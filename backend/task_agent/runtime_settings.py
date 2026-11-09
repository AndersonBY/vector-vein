"""Durable user changes to a task's model and approval mode, separate from frozen capabilities."""
from __future__ import annotations

import json

from vv_agent.model_settings import ModelSettings

from .client import TaskAgentError
from .config import build_model_snapshot, current_llm_settings, resolve_snapshot
from .permissions import validate_permission_mode
from .service import TaskConflict, required_id
from .store import now

CHANGE_METHOD = "desktop/runtime_settings"


def settings_for(task):
    return dict(task["config_snapshot"].get("runtime_settings") or {})


def permission_mode(task):
    return settings_for(task).get("permission_mode", task["config_snapshot"].get("agent_profile", {}).get("permission_mode"))


def selected_model_snapshot(store, task):
    change_id = settings_for(task).get("model_change_id")
    if change_id:
        change = store.command(task["tid"], change_id)
        if not change or change["method"] != CHANGE_METHOD or not change["params"].get("model_snapshot"):
            raise ValueError("Saved task model change is unavailable")
        return change["params"]["model_snapshot"]
    return task["config_snapshot"]


def public_settings(store, task):
    current = settings_for(task)
    snapshot = selected_model_snapshot(store, task)
    return {
        "revision": current.get("revision", 0),
        "permission_mode": permission_mode(task) or "ask",
        "model_provider": snapshot.get("display_provider", task["model_provider"]),
        "model": snapshot.get("requested_model", task["model"]),
        "reasoning_effort": snapshot.get("reasoning_effort", task["reasoning_effort"]),
        "context_length": snapshot.get("context_length"),
        "pending_change_id": current.get("pending_change_id"),
        "model_change_id": current.get("model_change_id"),
        "last_change_id": current.get("last_change_id"),
    }


def _write_settings(connection, task, settings):
    snapshot = {**task["config_snapshot"], "runtime_settings": settings}
    connection.execute("UPDATE tasks SET config_snapshot=?,updated_at=? WHERE tid=?", (json.dumps(snapshot, ensure_ascii=False), now(), task["tid"]))


def admit_change(store, payload):
    allowed = {"task_id", "request_id", "expected_revision", "permission_mode", "model_provider", "model", "reasoning_effort"}
    if not isinstance(payload, dict) or set(payload) - allowed:
        raise ValueError("Invalid task settings request")
    tid = required_id(payload.get("task_id"), "task ID")
    change_id = required_id(payload.get("request_id"), "settings request ID")
    revision = payload.get("expected_revision")
    if type(revision) is not int or revision < 0:
        raise ValueError("Invalid task settings revision")
    request = {key: value for key, value in payload.items() if key not in {"task_id", "request_id"}}
    if "permission_mode" in request:
        validate_permission_mode(request["permission_mode"])
    has_model = bool(set(request) & {"model_provider", "model", "reasoning_effort"})
    if not has_model and "permission_mode" not in request:
        raise ValueError("No task settings supplied")
    existing = store.command(tid, change_id)
    if existing:
        if existing["method"] != CHANGE_METHOD or existing["params"].get("request") != request:
            raise TaskConflict("This settings request already has different content")
        return existing
    snapshot = None
    if has_model:
        settings = current_llm_settings()
        snapshot = build_model_snapshot(settings, request.get("model_provider"), request.get("model"), request.get("reasoning_effort", "default"))
        if settings["backends"][snapshot["backend"]]["models"][snapshot["selected_model"]].get("enabled") is False:
            raise ValueError("Selected model is disabled")
        resolve_snapshot(snapshot, settings)
    params = {"request": request, "model_snapshot": snapshot}
    with store.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        task_row = connection.execute("SELECT * FROM tasks WHERE tid=?", (tid,)).fetchone()
        if task_row is None:
            raise KeyError(tid)
        task = store._task(task_row)
        previous = connection.execute("SELECT method,params FROM task_commands WHERE task_id=? AND command_id=?", (tid, change_id)).fetchone()
        if previous:
            if previous["method"] != CHANGE_METHOD or json.loads(previous["params"]) != params:
                raise TaskConflict("This settings request already has different content")
        else:
            current = settings_for(task)
            if current.get("pending_change_id") or current.get("revision", 0) != revision:
                raise TaskConflict("Task settings changed. Refresh before saving.")
            connection.execute("INSERT INTO task_commands VALUES(?,?,?,?,NULL)", (tid, change_id, CHANGE_METHOD, json.dumps(params, ensure_ascii=False)))
            _write_settings(connection, task, {**current, "pending_change_id": change_id})
    return store.command(tid, change_id)


def apply_pending_change(store, process, tid):
    task = store.get_task(tid)
    if task is None:
        raise KeyError(tid)
    change_id = settings_for(task).get("pending_change_id")
    if not change_id:
        return
    command = store.command(tid, change_id)
    if not command or command["method"] != CHANGE_METHOD:
        raise ValueError("Pending task settings are unavailable")
    params = command["params"]
    model_snapshot = params.get("model_snapshot")
    if model_snapshot:
        effort = model_snapshot.get("reasoning_effort", "default")
        selection = {
            "model": model_snapshot["model_id"],
            "model_settings": ModelSettings(reasoning={"effort": effort} if effort != "default" else None).to_dict(),
            "route": {"desktop_task_id": tid, "desktop_change_id": change_id},
        }
        process.start()
        try:
            result = process.request("thread/model/select", {"threadId": task["thread_id"], "inputId": change_id, "selection": selection})
        except TaskAgentError as error:
            if error.code == -32602:
                _finish_change(store, tid, change_id, accepted=False)
            raise
        if not isinstance(result, dict) or result.get("accepted") is not True or result.get("inputId") != change_id or result.get("threadId") != task["thread_id"]:
            raise TaskAgentError("Task model change was not confirmed")
    _finish_change(store, tid, change_id, accepted=True)


def _finish_change(store, tid, change_id, *, accepted):
    with store.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        task_row = connection.execute("SELECT * FROM tasks WHERE tid=?", (tid,)).fetchone()
        if task_row is None:
            raise KeyError(tid)
        task = store._task(task_row)
        current = settings_for(task)
        if current.get("pending_change_id") != change_id:
            raise TaskConflict("Task settings changed while saving")
        row = connection.execute("SELECT params FROM task_commands WHERE task_id=? AND command_id=?", (tid, change_id)).fetchone()
        params = json.loads(row["params"])
        current.pop("pending_change_id", None)
        if accepted:
            if "permission_mode" in params["request"]:
                current["permission_mode"] = params["request"]["permission_mode"]
                pending = store.projection(tid)["state"].get("pendingInteraction") or {}
                if pending.get("kind") == "approval" and pending.get("requestId"):
                    current["preserved_approval_id"] = pending["requestId"]
            if params.get("model_snapshot"):
                current["model_change_id"] = change_id
            current["revision"] = current.get("revision", 0) + 1
            current["last_change_id"] = change_id
        _write_settings(connection, task, current)
        connection.execute("UPDATE task_commands SET receipt=? WHERE task_id=? AND command_id=?", (json.dumps({"accepted": accepted}), tid, change_id))


def resolve_selection(store, request):
    route = request.get("route") or {}
    if set(route) != {"desktop_task_id", "desktop_change_id"}:
        raise ValueError("Invalid task model route")
    tid = required_id(route["desktop_task_id"], "task ID")
    change_id = required_id(route["desktop_change_id"], "model change ID")
    command = store.command(tid, change_id)
    if not store.get_task(tid) or not command or command["method"] != CHANGE_METHOD:
        raise ValueError("Task model change is not authorized")
    snapshot = command["params"].get("model_snapshot")
    if not snapshot or request.get("model") != snapshot["model_id"] or command["receipt"] == {"accepted": False}:
        raise ValueError("Task model does not match its saved selection")
    return snapshot
