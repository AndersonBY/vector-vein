"""Durable HumanFeedback checkpoints for the local workflow runner."""
from copy import deepcopy

from models import WorkflowRunRecord, Message
from utilities.config import cache
from utilities.workflow_timeline import merge_timeline


CHECKPOINT_FIELDS = ("pending_feedback_nodes", "pending_feedback_runs", "feedback_answers", "feedback_generation", "_feedback_waiting", "feedback_resume_ready")


class WorkflowPaused(Exception):
    def __init__(self, child_rid=None):
        self.child_rid = child_rid


def pause_requested(data):
    from utilities.workflow_stopping import _record
    record = _record(data.get("rid"))
    return record is not None and (record.status == "PAUSED" or record.data.get("_feedback_waiting", False))


def request_pause(data, node_id=None, child_rid=None):
    from utilities.workflow_stopping import _record, TERMINAL
    with cache.transact():
        record = _record(data.get("rid"))
        if record is None or record.status in (*TERMINAL, "STOPPING"):
            return
        saved = deepcopy(record.data)
        field, identity = ("pending_feedback_runs", child_rid) if child_rid else ("pending_feedback_nodes", node_id)
        if identity and identity not in saved.setdefault(field, []):
            saved[field].append(identity)
        saved["_feedback_waiting"] = True
        WorkflowRunRecord.update(data=saved).where(WorkflowRunRecord.rid == record.rid).execute()
        for key in CHECKPOINT_FIELDS:
            if key in saved:
                data[key] = deepcopy(saved[key])


def _project_pause(record):
    if record.run_from == WorkflowRunRecord.RunFromTypes.CHAT:
        message = Message.get_or_none(Message.mid == record.source_message)
        if message and message.status == Message.StatusTypes.RUNNING_WORKFLOW:
            message.metadata = {**message.metadata, "recordStatus": "PAUSED"}
            message.save()


def finish_pausing(rid):
    """Called under the admission transaction, after checkpoint snapshots are saved."""
    from utilities.workflow_stopping import _record, _key
    record = _record(rid)
    if record is None or record.status not in ("RUNNING", "QUEUED") or not record.data.get("_feedback_waiting"):
        return
    if cache.get(_key(rid, "active"), 0):
        return
    data = deepcopy(record.data)
    merge_timeline(data)
    changed = WorkflowRunRecord.update(status="PAUSED", data=data).where(
        WorkflowRunRecord.rid == rid, WorkflowRunRecord.status == record.status).execute()
    if changed:
        cache.set(f"workflow:record:{rid}", 102, 60 * 60)
        record.status, record.data = "PAUSED", data
        try:
            _project_pause(record)
        except Exception:
            pass
        parent = cache.get(_key(rid, "parent"))
        if parent:
            request_pause({"rid": parent}, child_rid=rid)
            finish_pausing(parent)


def _activate(record, answers):
    data = deepcopy(record.data)
    from utilities.workflow_recovery import claim_execution
    claim_execution(data)
    data.setdefault("feedback_answers", {}).update(answers)
    for node in data.get("nodes", []):
        if node["id"] in answers:
            node["data"]["template"].setdefault("human_input", {})["value"] = answers[node["id"]]
    data.update(pending_feedback_nodes=[], pending_feedback_runs=[], _feedback_waiting=False,
                feedback_generation=data.get("feedback_generation", 0) + 1, feedback_resume_ready=False)
    WorkflowRunRecord.update(status="RUNNING", data=data, end_time=None).where(
        WorkflowRunRecord.rid == record.rid, WorkflowRunRecord.status == "PAUSED").execute()
    cache.set(f"workflow:record:{record.rid.hex}", 202, 60 * 60)
    if record.run_from == WorkflowRunRecord.RunFromTypes.CHAT:
        try:
            message = Message.get_or_none(Message.mid == record.source_message)
            if message and message.status == Message.StatusTypes.RUNNING_WORKFLOW:
                message.metadata = {**message.metadata, "recordStatus": "RUNNING"}
                message.save()
        except Exception:
            pass
    return data


def _dispatch(data):
    from celery_tasks import run_workflow
    from utilities.workflow_stopping import _record, _key
    try:
        run_workflow.delay(data)
    except Exception:
        with cache.transact():
            record = _record(data["rid"])
            if record and record.status == "RUNNING" and not cache.get(_key(data["rid"], "active"), 0):
                # Publishing may have succeeded: retain every result already checkpointed.
                restored = deepcopy(record.data)
                restored.update(_feedback_waiting=True, feedback_resume_ready=True)
                WorkflowRunRecord.update(status="PAUSED", data=restored).where(
                    WorkflowRunRecord.rid == record.rid, WorkflowRunRecord.status == "RUNNING").execute()
                cache.set(f"workflow:record:{data['rid']}", 102, 60 * 60)
                record.status, record.data = "PAUSED", restored
                try:
                    _project_pause(record)
                except Exception:
                    pass
        raise


def resume_run(rid, submissions):
    from utilities.workflow_stopping import _record, _key
    with cache.transact():
        record = _record(rid)
        if record is None:
            return 404, "record not found", None
        if record.status != "PAUSED" or cache.get(_key(rid, "active"), 0):
            return 409, "only a drained paused run can be resumed", record
        pending = record.data.get("pending_feedback_nodes", [])
        children = [_record(child_id) for child_id in record.data.get("pending_feedback_runs", [])]
        children_done = all(child and child.status == "FINISHED" for child in children)
        ready = bool(record.data.get("feedback_resume_ready")) and children_done
        if (not pending and not ready) or not children_done:
            return 409, "resume the pending child runs first", record
        if not isinstance(submissions, list) or (not submissions and not ready):
            return 400, "feedback is required", record
        answers = {}
        for entry in submissions:
            if not isinstance(entry, dict):
                return 400, "invalid feedback entry", record
            node_id, content = entry.get("node_id"), entry.get("content")
            if not isinstance(node_id, str) or node_id not in pending or node_id in answers:
                return 400, "feedback must identify each pending node exactly once", record
            if not isinstance(content, str) or not content.strip():
                return 400, "human input must not be blank", record
            answers[node_id] = content
        if set(answers) != set(pending):
            return 400, "feedback is required for every pending node", record
        data = _activate(record, answers)
    try:
        _dispatch(data)
    except Exception:
        return 500, "could not dispatch resumed workflow", _record(rid)
    return 200, "RUNNING", _record(rid)


def wake_parent(rid):
    """Child completion wakes a checkpointed parent without consuming poll retries."""
    from utilities.workflow_stopping import _record, _key, request_stop, TERMINAL
    with cache.transact():
        parent_rid = cache.get(_key(rid, "parent"))
        parent = _record(parent_rid)
        if parent is None or parent.status != "PAUSED" or cache.get(_key(parent_rid, "active"), 0):
            return
        children = [_record(child_id) for child_id in parent.data.get("pending_feedback_runs", [])]
        if not children or any(child is None for child in children):
            return
        failed = next((child for child in children if child.status == "FAILED"), None)
        if failed:
            request_stop(parent_rid)
            return
        if any(child.status == "STOPPED" for child in children):
            request_stop(parent_rid)
            return
        if any(child.status not in TERMINAL for child in children):
            return
        if parent.data.get("pending_feedback_nodes"):
            data = deepcopy(parent.data)
            data["pending_feedback_runs"] = []
            WorkflowRunRecord.update(data=data).where(WorkflowRunRecord.rid == parent.rid).execute()
            return
        data = _activate(parent, {})
    try:
        _dispatch(data)
    except Exception:
        # The checkpoint remains resumable if publishing could not be confirmed.
        pass
