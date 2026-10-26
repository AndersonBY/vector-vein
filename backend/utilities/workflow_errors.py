"""Bounded, redacted execution failures shared by desktop workflow consumers."""
import re


MAX_FAILURES = 8
MAX_MESSAGE_LENGTH = 1500
_SECRET_KEY = re.compile(r"api[_-]?key|private[_-]?key|access[_-]?key|password|passwd|secret|token|authorization|credential|cookie|signature", re.I)


class WorkflowInputError(ValueError):
    """An explicitly identified, user-correctable node input error."""


class WorkflowExecutionError(RuntimeError):
    """Propagate a failed child workflow without replacing its diagnostics."""

    def __init__(self, failures):
        self.failures = [item for item in failures if isinstance(item, dict)][:MAX_FAILURES]
        super().__init__(self.failures)

    def __str__(self):
        return self.failures[0].get("message", "Workflow execution failed") if self.failures else "Workflow execution failed"


def _secret_values(value, sensitive=False, node_template=False):
    if hasattr(value, "get_secret_value"):
        yield str(value.get_secret_value())
        return
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if isinstance(value, dict):
        for key, item in value.items():
            secret_key = bool(_SECRET_KEY.search(str(key)))
            if node_template and secret_key and isinstance(item, dict) and "value" in item:
                yield from _secret_values(item["value"], True)
            else:
                yield from _secret_values(item, sensitive or secret_key, key == "template")
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _secret_values(item, sensitive)
    elif sensitive and isinstance(value, (str, int)) and str(value):
        yield str(value)


def redact_message(message, workflow_data=None):
    text = str(message)
    sources = [workflow_data or {}]
    try:
        from utilities.config import Settings
        sources.append(Settings().data)
    except Exception:
        pass
    secrets = {secret for source in sources for secret in _secret_values(source) if secret}
    for secret in sorted(secrets, key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[REDACTED]@", text, flags=re.I)
    text = re.sub(r"\b(Bearer|Basic)\s+[^\s,'\"}\]]+", r"\1 [REDACTED]", text, flags=re.I)
    text = re.sub(r"([\"']?(?:[\w-]*(?:api[_-]?key|private[_-]?key|access[_-]?key|password|passwd|secret|token|authorization|credential|cookie|signature))[\"']?\s*[:=]\s*)[\"']?[^\s,;&\"'}\]]+", r"\1[REDACTED]", text, flags=re.I)
    return text[:MAX_MESSAGE_LENGTH]


def node_failure(exc, workflow_data, node_id="", task_name=""):
    return {"node_id": node_id or "", "task_name": task_name.removeprefix("tasks."),
            "code": "INVALID_ARGUMENT" if isinstance(exc, WorkflowInputError) else "NODE_EXECUTION_FAILED",
            "exception_type": type(exc).__name__, "message": redact_message(exc, workflow_data)}


def add_failure(workflow_data, failure):
    failures = workflow_data.get("failures", [])
    if not isinstance(failures, list):
        failures = []
    if failure not in failures:
        failures.append(failure)
    workflow_data["failures"] = failures[:MAX_FAILURES]


def workflow_error_payload(record):
    data = (record.get("data", {}) if isinstance(record, dict) else record.data) or {}
    stored = data.get("failures", [])
    failures = []
    if isinstance(stored, list):
        for failure in stored:
            if not isinstance(failure, dict):
                continue
            failures.append({
                "node_id": redact_message(failure.get("node_id", ""), data)[:200],
                "task_name": redact_message(failure.get("task_name", ""), data)[:200],
                "code": "INVALID_ARGUMENT" if failure.get("code") == "INVALID_ARGUMENT" else "NODE_EXECUTION_FAILED",
                "exception_type": redact_message(failure.get("exception_type", ""), data)[:200],
                "message": redact_message(failure.get("message", "Workflow execution failed"), data),
            })
            if len(failures) == MAX_FAILURES:
                break
    if not failures:
        failures = [{"node_id": "", "task_name": redact_message(data.get("error_task", ""), data)[:200],
                     "code": "NODE_EXECUTION_FAILED", "exception_type": redact_message(data.get("error_type", ""), data)[:200],
                     "message": "Workflow execution failed; inspect the run record for details."}]
    rid = record.get("rid", "") if isinstance(record, dict) else getattr(record, "rid", data.get("rid", ""))
    status = record.get("status", "FAILED") if isinstance(record, dict) else record.status
    return {"error": "WORKFLOW_FAILED", "rid": getattr(rid, "hex", rid),
            "status": status, "failures": failures,
            "next_action": "inspect_error", "replay_safety": "unknown"}
