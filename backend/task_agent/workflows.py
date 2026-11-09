"""Approved workflow jobs bound to vv-agent's public Provider contract."""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError
from vv_agent import FunctionTool
from vv_agent.session.providers import Accepted, Definitive, Unknown
from vv_agent.tools.metadata import ToolMetadata
from vv_agent.types import ToolExecutionResult, ToolResultStatus

from .store import BusinessStore

TERMINAL = {"FINISHED", "FAILED", "STOPPED"}
MAX_ARTIFACT_BYTES = 50 * 1024 * 1024


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def workflow_descriptor(workflow):
    from utilities.workflow import WorkflowData
    properties, sources, required = {}, {}, []
    saved = workflow.tool_call_data or {}
    for index, field in enumerate(WorkflowData(deepcopy(workflow.data)).ui_design["input_fields"]):
        key = next((name for name, source in saved.get("parameter_sources", {}).items()
                    if source.get("node") == field["nodeId"] and source.get("field") == field["fieldName"]), field["fieldName"])
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", key):
            key = f"input_{index + 1}"
        base, suffix = key, 2
        while key in properties:
            key = f"{base[:58]}_{suffix}"
            suffix += 1
        kind = str(field.get("type", "str")).split("|")[0]
        schema = {"type": {"int": "integer", "float": "number", "bool": "boolean"}.get(kind, "string"),
                  "description": str(field.get("display_name") or field.get("name") or field["fieldName"])}
        if kind in {"dict", "list"}:
            schema["description"] += " (JSON text)"
        options = field.get("options")
        if field.get("list") and isinstance(options, list) and options:
            schema["enum"] = [option["value"] for option in options if isinstance(option, dict) and "value" in option]
        properties[key] = schema
        sources[key] = {"node": field["nodeId"], "field": field["fieldName"], "kind": kind}
        if field.get("value") in (None, ""):
            required.append(key)
    return {
        "workflow_id": workflow.wid.hex, "version": workflow.version, "title": workflow.title,
        "description": workflow.brief[:2000], "definition_digest": digest(workflow.data),
        "tool_name": "workflow_" + workflow.wid.hex, "sources": sources,
        "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False},
    }


def selected_workflows(ids):
    if ids == []:
        return []
    from models import Workflow
    if not isinstance(ids, list) or len(ids) > 20 or not all(isinstance(value, str) for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("Select at most 20 distinct workflows")
    identities = [uuid.UUID(value).hex for value in ids]
    if len(set(identities)) != len(identities):
        raise ValueError("Workflow identities must be distinct")
    result = []
    for identity in identities:
        workflow = Workflow.get_or_none((Workflow.wid == identity) & (Workflow.status == "VALID"))
        if workflow is None:
            raise ValueError("Selected workflow is unavailable")
        result.append(workflow_descriptor(workflow))
    return result


def workflow_catalog():
    from models import Workflow
    return [{"workflow_id": workflow.wid.hex, "title": workflow.title, "description": workflow.brief[:500], "version": workflow.version}
            for workflow in Workflow.select().where(Workflow.status == "VALID").order_by(Workflow.update_time.desc())]


def _unbound(_context, _arguments):
    raise RuntimeError("Workflow jobs require the desktop provider binding")


def workflow_tools(descriptors):
    return [FunctionTool(name=item["tool_name"], description=f"Run workflow: {item['title']}. {item['description']}",
                         params_json_schema=deepcopy(item["parameters"]), on_invoke=_unbound,
                         strict_json_schema=False, needs_approval=True,
                         tool_metadata=ToolMetadata(side_effect="execute", idempotency="supported")) for item in descriptors]


class WorkflowProvider:
    def __init__(self, task_root: Path, task_id: str, workspace: Path, descriptor: dict):
        self.store = BusinessStore(task_root / "tasks.db")
        self.task_id = task_id
        self.workspace = workspace
        self.descriptor = descriptor

    def _handle(self, job):
        return {"kind": "provider", "provider": job["payload"]["provider"], "job_id": job["job_id"],
                "operation_id": job["payload"]["operation_id"], "attempt": job["payload"]["attempt"],
                "request_digest": job["payload"]["request_digest"], "evidence": job["payload"]["evidence"],
                "query_ref": job["run_id"], "cancel_ref": job["run_id"]}

    def _job(self, handle):
        job = self.store.workflow_job(handle.get("job_id"))
        if job is None or job["task_id"] != self.task_id or self._handle(job) != handle:
            return None
        return job

    def submit(self, plan, *, context):
        from api.utils import run_workflow_common
        from models import Workflow, WorkflowRunRecord
        payload = plan.payload
        identity = digest([self.task_id, plan.operation_id, plan.attempt])
        run_id = uuid.uuid5(uuid.NAMESPACE_URL, "vectorvein-task-workflow:" + identity).hex
        job_payload = {"operation_id": plan.operation_id, "attempt": plan.attempt, "request_digest": payload["request_digest"],
                       "provider": payload["provider_binding"], "tool_call_id": payload["request"]["id"],
                       "turn_id": plan.turn_id, "workflow_id": self.descriptor["workflow_id"], "title": self.descriptor["title"],
                       "evidence": "workflow-admission:" + identity, "arguments": payload["request"]["arguments"]}
        existing = self.store.workflow_job(identity)
        if existing is not None:
            if {key: value for key, value in existing["payload"].items() if key != "dispatch_uncertain"} != job_payload or existing["task_id"] != self.task_id:
                return Unknown("Workflow submission identity conflict")
            return self.query(self._handle(existing))
        arguments = job_payload["arguments"]
        try:
            Draft202012Validator(self.descriptor["parameters"]).validate(arguments)
            workflow = Workflow.get_or_none((Workflow.wid == self.descriptor["workflow_id"]) & (Workflow.status == "VALID"))
            if workflow is None or workflow.version != self.descriptor["version"] or digest(workflow.data) != self.descriptor["definition_digest"]:
                return Definitive(ToolExecutionResult(tool_call_id=job_payload["tool_call_id"], status_code=ToolResultStatus.ERROR,
                                  error_code="workflow_changed", content="The selected workflow changed or is unavailable. Create a new task to use its current configuration.").to_dict())
            data = deepcopy(workflow.data)
            for name, value in arguments.items():
                source = self.descriptor["sources"][name]
                if source["kind"] in {"dict", "list"}:
                    value = json.loads(value)
                    if not isinstance(value, dict if source["kind"] == "dict" else list):
                        raise ValueError("Invalid structured workflow input")
                if source["kind"] == "file":
                    value = str(context.resolve_workspace_path(value))
                node = next(n for n in data["nodes"] if n["id"] == source["node"])
                node["data"]["template"][source["field"]]["value"] = value
        except (ValueError, ValidationError, KeyError, StopIteration):
            return Definitive(ToolExecutionResult(tool_call_id=job_payload["tool_call_id"], status_code=ToolResultStatus.ERROR,
                              error_code="workflow_input_invalid", content="Workflow inputs are invalid. Follow the declared schema; structured values must be valid JSON and files must be inside the task workspace.").to_dict())
        job = self.store.add_workflow_job(self.task_id, identity, run_id, job_payload)
        if {key: value for key, value in job["payload"].items() if key != "dispatch_uncertain"} != job_payload:
            return Unknown("Workflow submission identity conflict")
        try:
            run_workflow_common(data, workflow, run_from=WorkflowRunRecord.RunFromTypes.API,
                                workflow_version=self.descriptor["version"], record_id=run_id, submission_key=identity)
        except Exception:
            # Publication may have succeeded. Only the durable run can settle its outcome.
            self.store.mark_workflow_dispatch_uncertain(identity)
        return self.query(self._handle(job))

    def query(self, handle):
        from models import WorkflowRunRecord
        job = self._job(handle)
        if job is None:
            return Unknown("Workflow binding not found")
        if job["result"] is not None:
            return Definitive(job["result"], (handle["evidence"],))
        record = WorkflowRunRecord.get_or_none(WorkflowRunRecord.rid == job["run_id"])
        if record is None:
            return Unknown("Workflow admission could not be confirmed; no automatic resubmission")
        if record.data.get("_task_agent_submission") != job["job_id"]:
            return Unknown("Workflow run identity mismatch")
        if record.status not in TERMINAL:
            return Accepted(handle)
        result = self._result(job, record)
        return Definitive(self.store.finish_workflow_job(job["job_id"], result), (handle["evidence"],))

    def cancel(self, handle):
        from utilities.workflow_stopping import request_stop
        job = self._job(handle)
        if job is None:
            return Unknown("Workflow binding not found")
        outcome = self.query(handle)
        if not isinstance(outcome, Accepted):
            return outcome
        request_stop(job["run_id"])
        return self.query(handle)

    def authenticate(self, item, plan):
        # This local adapter settles work by authenticated database reads, not external callbacks.
        return False

    def _result(self, job, record):
        from utilities.workflow import WorkflowData
        from utilities.workflow_artifacts import get_run_artifacts
        files, unavailable = [], []
        for index, artifact in enumerate(get_run_artifacts(record.data)):
            source = Path(artifact["path"])
            destination = self.workspace / "outputs" / "workflows" / job["run_id"] / f"{index + 1}-{source.name}"
            try:
                if index >= 20 or not artifact["exists"] or source.stat().st_size > MAX_ARTIFACT_BYTES:
                    raise ValueError("Artifact unavailable or exceeds the copy limit")
                if not destination.resolve().is_relative_to(self.workspace.resolve()):
                    raise ValueError("Artifact destination escapes workspace")
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_name(destination.name + "." + uuid.uuid4().hex + ".tmp")
                try:
                    with source.open("rb") as incoming, temporary.open("xb") as output:
                        remaining = MAX_ARTIFACT_BYTES
                        while chunk := incoming.read(min(65536, remaining + 1)):
                            remaining -= len(chunk)
                            if remaining < 0:
                                raise ValueError("Artifact exceeds the copy limit")
                            output.write(chunk)
                    os.replace(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)
                files.append({"name": source.name, "path": destination.relative_to(self.workspace).as_posix()})
            except (OSError, ValueError):
                unavailable.append(source.name)
        content = {"run_id": job["run_id"], "workflow": job["payload"]["title"], "status": record.status,
                   "outputs": WorkflowData(deepcopy(record.data)).output_contents, "files": files, "unavailable_files": unavailable}
        if record.status != "FINISHED":
            content["failures"] = [{key: failure.get(key) for key in ("node_id", "code", "message")}
                                   for failure in record.data.get("failures", [])[:10] if isinstance(failure, dict)]
        return ToolExecutionResult(tool_call_id=job["payload"]["tool_call_id"],
                                   status_code=ToolResultStatus.SUCCESS if record.status == "FINISHED" else ToolResultStatus.ERROR,
                                   error_code=None if record.status == "FINISHED" else "workflow_" + record.status.lower(),
                                   content=json.dumps(content, ensure_ascii=False), metadata={"output_type": "json"}).to_dict()


def workflow_run_views(store, task_id):
    jobs = store.workflow_jobs(task_id)
    if not jobs:
        return []
    from models import WorkflowRunRecord
    result = []
    for job in jobs:
        record = WorkflowRunRecord.get_or_none(WorkflowRunRecord.rid == job["run_id"])
        view = {"job_id": job["job_id"], "run_id": job["run_id"], "title": job["payload"]["title"],
                "workflow_id": job["payload"]["workflow_id"], "tool_call_id": job["payload"]["tool_call_id"],
                "status": record.status if record else json.loads(job["result"]["content"]).get("status", "UNKNOWN") if job["result"] else "UNKNOWN", "feedback": []}
        if record is not None:
            started = any(item.get("started_at") is not None for item in record.data.get("node_timeline", {}).values())
            if job["payload"].get("dispatch_uncertain") and not started and record.status not in TERMINAL:
                view["status"] = "UNKNOWN"
            view["feedback"] = _feedback_views(record)
        result.append(view)
    return result


def _feedback_views(record, seen=None):
    from models import WorkflowRunRecord
    seen = set() if seen is None else seen
    if record.rid.hex in seen or len(seen) >= 100:
        return []
    seen.add(record.rid.hex)
    result = []
    if record.status == "PAUSED":
        nodes = {node["id"]: node for node in record.data.get("nodes", [])}
        questions = [{"node_id": identity, "prompt": nodes[identity]["data"]["template"].get("hint_message", {}).get("value", "")}
                     for identity in record.data.get("pending_feedback_nodes", []) if identity in nodes]
        children = [WorkflowRunRecord.get_or_none(WorkflowRunRecord.rid == child_id) for child_id in record.data.get("pending_feedback_runs", [])]
        children_done = all(child and child.status == "FINISHED" for child in children)
        if children_done and (questions or record.data.get("feedback_resume_ready")):
            result.append({"run_id": record.rid.hex, "generation": record.data.get("feedback_generation", 0),
                           "questions": questions, "resume_ready": bool(record.data.get("feedback_resume_ready"))})
        for child in children:
            if child is not None:
                result.extend(_feedback_views(child, seen))
    return result


def resume_workflow(store, task_id, payload):
    from utilities.workflow_feedback import resume_run
    from models import WorkflowRunRecord
    # A submitted reply stays bound to a run admitted by this task, including its actual children.
    roots = {job["run_id"] for job in store.workflow_jobs(task_id)}
    allowed = set()
    pending = list(roots)
    while pending and len(allowed) < 100:
        run_id = pending.pop()
        if run_id in allowed:
            continue
        allowed.add(run_id)
        record = WorkflowRunRecord.get_or_none(WorkflowRunRecord.rid == run_id)
        if record:
            from utilities.config import cache
            pending.extend(cache.get(f"workflow:record:{run_id}:stop:children", []))
    if payload.get("run_id") not in allowed:
        raise ValueError("Workflow does not belong to this task")
    generation = payload.get("generation")
    if type(generation) is not int or generation < 0:
        raise ValueError("Workflow checkpoint generation required")
    status, message, _ = resume_run(payload["run_id"], payload.get("answers"),
                                    expected_generation=generation, submission_id=payload["action_id"])
    return {"status": status, "message": message}
