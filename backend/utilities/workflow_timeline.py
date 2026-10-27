"""Small per-run node progress snapshots; cache failures never affect execution."""
import time
from copy import deepcopy

from utilities.config import cache


TTL = 24 * 60 * 60


def _key(data):
    rid = data.get("rid")
    return f"workflow:record:node_timeline:{rid}" if isinstance(rid, str) and rid else None


def _entry(node):
    metadata = node.get("data", {})
    entry = {
        "node_id": node["id"], "node_type": node.get("type", ""),
        "task_name": metadata.get("task_name", ""), "status": "PENDING",
        "started_at": None, "finished_at": None, "run_time": None,
    }
    if isinstance(metadata.get("title"), str):
        entry["title"] = metadata["title"][:200]
    return entry


def reset_run(data):
    data.pop("_execution_owners", None)
    for key in ("failures", "error_task", "error_type", "skipped_nodes", "node_run_time", "node_timeline", "original_workflow_data", "async_tasks", "__node_id_map", "_batch_collecting", "pending_feedback_nodes", "pending_feedback_runs", "feedback_answers", "feedback_generation", "_feedback_waiting", "feedback_resume_ready"):
        data.pop(key, None)
    for node in data.get("nodes", []):
        node.setdefault("data", {})["artifacts"] = []
        for key in ("status", "run_time", "started_at", "finished_at"):
            node.pop(key, None)
            node.get("data", {}).pop(key, None)
    for related in data.get("related_workflows", {}).values():
        if isinstance(related, dict):
            reset_run(related)
    # Use the same DAG as execution, including isolated runnable nodes.
    from utilities.workflow import Workflow
    workflow = Workflow(deepcopy(data))
    runnable = workflow.dag.get_all_nodes()
    data["node_timeline"] = {
        node["id"]: _entry(node) for node in data.get("nodes", [])
        if node["id"] in runnable and not node.get("ignored")
        and node.get("category") not in ("triggers", "assistedNodes")
    }


def read_timeline(data):
    local = data.get("node_timeline")
    result = deepcopy(local) if isinstance(local, dict) else {}
    try:
        if _key(data):
            result.update(cache.get(_key(data), {}))
    except Exception:
        pass
    return result


def initialize_timeline(data):
    try:
        if _key(data):
            cache.set(_key(data), data.get("node_timeline", {}), TTL)
    except Exception:
        pass


def update_timeline(data, node_id, status):
    try:
        _update_timeline(data, node_id, status)
    except Exception:
        # Progress must never replace a task result or its original exception.
        pass


def _update_timeline(data, node_id, status):
    node = next((node for node in data.get("nodes", []) if node.get("id") == node_id), None)
    if node is None:
        return
    now = int(time.time() * 1000)

    def update(current):
        previous = current.get(node_id)
        if not isinstance(previous, dict):
            local_timeline = data.get("node_timeline")
            previous = local_timeline.get(node_id) if isinstance(local_timeline, dict) else None
        entry = _entry(node)
        if isinstance(previous, dict):
            for key in ("status", "started_at", "finished_at", "run_time"):
                if key in previous:
                    entry[key] = previous[key]
        entry["status"] = status
        if status in ("RUNNING", "WAITING") and entry["started_at"] is None:
            entry["started_at"] = now
        if status in ("SUCCEEDED", "FAILED", "SKIPPED", "STOPPED"):
            entry["finished_at"] = now
            entry["run_time"] = max(0, (now - entry["started_at"]) / 1000) if entry["started_at"] is not None else None
        else:
            entry["finished_at"] = entry["run_time"] = None
        current[node_id] = entry
        return current

    # Only publish the changed node, never a stale sibling snapshot.
    local = data.get("node_timeline")
    local = update(deepcopy(local) if isinstance(local, dict) else {})
    data["node_timeline"] = local
    if not _key(data):
        return
    try:
        with cache.transact():
            merged = update(cache.get(_key(data), {}))
            cache.set(_key(data), merged, TTL)
        data["node_timeline"] = merged
    except Exception:
        pass


def merge_timeline(data):
    data["node_timeline"] = read_timeline(data)
