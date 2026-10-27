"""Cooperative run admission and draining, shared by the API and task workers."""
from copy import deepcopy
from datetime import datetime
from functools import wraps
from uuid import UUID

from celery import current_task

from models import WorkflowRunRecord, Message
from utilities.config import cache
from utilities.workflow_timeline import merge_timeline, update_timeline


TERMINAL = ("FINISHED", "FAILED", "STOPPED")


class WorkflowStopped(Exception):
    """A nested run stopped without producing a successful result."""


def _key(rid, suffix):
    return f"workflow:record:{rid}:stop:{suffix}"


def _record(rid):
    if not rid:
        return None
    try:
        normalized = UUID(str(rid)).hex
    except (ValueError, TypeError, AttributeError):
        return None
    return WorkflowRunRecord.get_or_none(WorkflowRunRecord.rid == normalized)


def _project_stopped(record):
    if record.run_from == WorkflowRunRecord.RunFromTypes.CHAT:
        message = Message.get_or_none(Message.mid == record.source_message)
        if message and message.status == Message.StatusTypes.RUNNING_WORKFLOW:
            message.metadata = {**message.metadata, "recordStatus": "STOPPED", "workflow_result": "Workflow stopped. Completed outputs are retained."}
            message.status = Message.StatusTypes.WORKFLOW_FAILED
            message.save()


def _finish_stopping(rid):
    record = _record(rid)
    if record is None or record.status != "STOPPING" or cache.get(_key(rid, "active"), 0):
        return
    children = [_record(child_id) for child_id in cache.get(_key(rid, "children"), [])]
    if any(child and child.status not in TERMINAL for child in children):
        return
    data = deepcopy(record.data)
    merge_timeline(data)
    failed = next((child for child in children if child and child.status == "FAILED"), None)
    if failed:
        from utilities.workflow import Workflow
        from utilities.workflow_errors import add_failure
        for failure in failed.data.get("failures", []):
            add_failure(data, failure)
        Workflow(data).report_workflow_status(500, "workflow.child")
        from utilities.workflow_feedback import wake_parent
        wake_parent(rid)
        parent = cache.get(_key(rid, "parent"))
        if parent:
            _finish_stopping(parent)
        return
    for node_id, entry in list(data.get("node_timeline", {}).items()):
        if entry.get("status") in ("PENDING", "WAITING", "RUNNING"):
            update_timeline(data, node_id, "STOPPED")
    changed = WorkflowRunRecord.update(status="STOPPED", data=data, end_time=datetime.now()).where(
        WorkflowRunRecord.rid == rid, WorkflowRunRecord.status == "STOPPING").execute()
    if changed:
        cache.set(f"workflow:record:{rid}", 200, 60 * 60)
        record.status, record.data = "STOPPED", data
        try:
            _project_stopped(record)
        except Exception:
            # The run's durable terminal state must survive chat projection failure.
            pass
        from utilities.workflow_feedback import wake_parent
        wake_parent(rid)
        parent = cache.get(_key(rid, "parent"))
        if parent:
            _finish_stopping(parent)


def request_stop(rid):
    with cache.transact():
        record = _record(rid)
        if record is None:
            return None
        if record.status not in TERMINAL:
            WorkflowRunRecord.update(status="STOPPING").where(
                WorkflowRunRecord.rid == rid, ~WorkflowRunRecord.status.in_(TERMINAL)).execute()
            for child in cache.get(_key(rid, "children"), []):
                request_stop(child)
            _finish_stopping(rid)
        result = _record(rid)
    from utilities.workflow_feedback import wake_parent
    wake_parent(rid)
    return result


def register_child(parent_rid, child_rid):
    """Called under the admission transaction before a child can be dispatched."""
    children = cache.get(_key(parent_rid, "children"), [])
    if child_rid not in children:
        cache.set(_key(parent_rid, "children"), [*children, child_rid])
    cache.set(_key(child_rid, "parent"), parent_rid)


def stop_requested(data):
    record = _record(data.get("rid"))
    return record is not None and record.status in ("STOPPING", "STOPPED")


def _clear_continuation():
    if current_task:
        current_task.request.chain = None


def guarded_execution(func):
    """Admit work atomically with stop; retain completed results before draining."""
    @wraps(func)
    def wrapped(*args, **kwargs):
        from utilities.workflow_feedback import CHECKPOINT_FIELDS, finish_pausing, pause_requested, wake_parent
        data = kwargs.get("workflow_data")
        if data is None:
            data = next((arg for arg in args if isinstance(arg, dict)), None)
        rid = data.get("rid") if isinstance(data, dict) else None
        node_id = kwargs.get("node_id")
        if node_id is None and len(args) > 1 and isinstance(args[1], str):
            node_id = args[1]
        with cache.transact():
            record = _record(rid)
            stale = record is not None and data.get("feedback_generation", 0) != record.data.get("feedback_generation", 0)
            waiting = record is not None and (record.status == "PAUSED" or record.data.get("_feedback_waiting") and not data.get("_batch_collecting"))
            completed = record is not None and node_id and record.data.get("node_timeline", {}).get(node_id, {}).get("status") in ("SUCCEEDED", "SKIPPED")
            if record is not None and (record.status in (*TERMINAL, "STOPPING") or stale or waiting or completed):
                _clear_continuation()
                return deepcopy(record.data) if stale or completed else data
            if record is not None:
                from utilities.workflow_recovery import claim_execution, OWNERS
                data[OWNERS] = record.data.get(OWNERS, [])
                claim_execution(data)
                saved = {**record.data, OWNERS: data[OWNERS]}
                WorkflowRunRecord.update(data=saved).where(WorkflowRunRecord.rid == rid).execute()
                cache.set(_key(rid, "active"), cache.get(_key(rid, "active"), 0) + 1)
        result = None
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            if record is not None:
                with cache.transact():
                    current = _record(rid)
                    snapshot = result if isinstance(result, dict) else data
                    if current and current.status not in TERMINAL and isinstance(snapshot, dict):
                        saved = deepcopy(current.data)
                        if node_id:
                            completed = next((node for node in snapshot.get("nodes", []) if node["id"] == node_id), None)
                            if completed:
                                saved["nodes"] = [deepcopy(completed) if node["id"] == node_id else node for node in saved.get("nodes", [])]
                            for field in ("node_run_time", "async_tasks"):
                                saved.setdefault(field, {}).update(snapshot.get(field, {}))
                        elif isinstance(result, dict):
                            saved = deepcopy(snapshot)
                        for field in CHECKPOINT_FIELDS:
                            if field in current.data:
                                saved[field] = deepcopy(current.data[field])
                        saved["rid"] = rid
                        if snapshot.get("wid"):
                            saved["wid"] = snapshot["wid"]
                        saved.pop("_batch_collecting", None)
                        saved[OWNERS] = list(current.data.get(OWNERS, []))
                        merge_timeline(saved)
                        WorkflowRunRecord.update(data=saved).where(
                            WorkflowRunRecord.rid == rid, ~WorkflowRunRecord.status.in_(TERMINAL)).execute()
                    cache.set(_key(rid, "active"), max(0, cache.get(_key(rid, "active"), 1) - 1))
                    _finish_stopping(rid)
                    finish_pausing(rid)
                    if stop_requested({"rid": rid}) or pause_requested({"rid": rid}):
                        _clear_continuation()
                    parent = cache.get(_key(rid, "parent"))
                    if parent:
                        _finish_stopping(parent)
                wake_parent(rid)
                current = _record(rid)
                if current and current.status == "PAUSED":
                    for child in current.data.get("pending_feedback_runs", []):
                        wake_parent(child)
    return wrapped
