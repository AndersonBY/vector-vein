"""Confirm process exit before finalizing interrupted local workflow runs."""
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from threading import Lock
from uuid import UUID, uuid4

from models import WorkflowRunRecord
from utilities.config import cache, config


OWNERS = "_execution_owners"
_lease = None
_lease_pid = None
_lease_id = None
_lease_guard = Lock()


def _lock(file):
    file.seek(0)
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _directory():
    return Path(config.data_path) / "execution-locks"


def process_owner():
    global _lease, _lease_pid, _lease_id
    with _lease_guard:
        if _lease is None or _lease_pid != os.getpid():
            if _lease is not None:
                _lease.close()
            _directory().mkdir(parents=True, exist_ok=True)
            identity = uuid4().hex
            lease = (_directory() / identity).open("w+b")
            lease.write(b"1")
            lease.flush()
            _lock(lease)
            _lease, _lease_pid, _lease_id = lease, os.getpid(), identity
        return _lease_id


def owner_exited(identity):
    try:
        if not isinstance(identity, str) or UUID(identity).hex != identity:
            return False
        with (_directory() / identity).open("r+b") as lease:
            _lock(lease)
        return True
    except FileNotFoundError:
        return True
    except (OSError, ValueError):
        return False


def claim_execution(data):
    stored = data.get(OWNERS)
    owners = list(stored) if isinstance(stored, list) else []
    identity = process_owner()
    if identity not in owners:
        owners.append(identity)
    data[OWNERS] = owners


def recover_interrupted_runs():
    """Preserve live/unknown owners and resumable feedback checkpoints."""
    from utilities.workflow_stopping import _key
    from utilities.workflow_timeline import merge_timeline, initialize_timeline, update_timeline
    from utilities.workflow_errors import add_failure
    from utilities.workflow_messages import project_workflow_message

    recovered = []
    with cache.transact():
        records = WorkflowRunRecord.select().where(WorkflowRunRecord.status.in_(("RUNNING", "QUEUED", "STOPPING")))
        for record in records:
            owners = record.data.get(OWNERS)
            # Legacy records have no evidence of process ownership; do not guess.
            if not isinstance(owners, list) or not owners or not all(owner_exited(owner) for owner in owners):
                continue
            data = deepcopy(record.data)
            rid = record.rid.hex
            data["rid"] = rid
            finished = cache.get(f"workflow:record:finished_nodes:{rid}", [])
            by_id = {node["id"]: node for node in finished if isinstance(node, dict) and "id" in node}
            data["nodes"] = [deepcopy(by_id.get(node["id"], node)) for node in data.get("nodes", [])]
            merge_timeline(data)
            initialize_timeline(data)
            for node_id, entry in list(data.get("node_timeline", {}).items()):
                if entry.get("status") in ("RUNNING", "WAITING", "PENDING"):
                    update_timeline(data, node_id, "FAILED")
            data.pop("_batch_collecting", None)
            add_failure(data, {"node_id": "", "task_name": "workflow.run", "code": "WORKFLOW_INTERRUPTED",
                "exception_type": "ExecutionInterrupted",
                "message": "The execution process exited before the workflow finished. Completed outputs and files are retained."})
            with WorkflowRunRecord._meta.database.atomic():
                changed = WorkflowRunRecord.update(status="FAILED", data=data, end_time=datetime.now()).where(
                    WorkflowRunRecord.rid == record.rid, WorkflowRunRecord.status == record.status).execute()
                if not changed:
                    continue
                record.status, record.data = "FAILED", data
            try:
                project_workflow_message(record)
            except Exception as exc:
                from utilities.general import mprint
                mprint.error(f"Interrupted workflow message update failed: {type(exc).__name__}")
            cache.set(_key(rid, "active"), 0)
            cache.set(f"workflow:record:{rid}", 500, 60 * 60)
            recovered.append(rid)
        # Let surviving paused parents observe an interrupted child without replaying it.
        from utilities.workflow_feedback import wake_parent
        for rid in recovered:
            wake_parent(rid)
    return recovered
