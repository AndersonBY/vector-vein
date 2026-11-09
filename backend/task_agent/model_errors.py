"""Credential-free observations of model failures; execution semantics stay with vv-agent."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import httpx
from openai import APIConnectionError, APITimeoutError
from vv_agent.llm.vv_llm_client import VvLlmClient

PARAMETERS = {"model", "max_tokens", "max_completion_tokens", "reasoning_effort", "tools", "tool_choice", "temperature", "response_format", "messages", "stream", "thinking", "top_p"}
CODES = {"invalid_api_key": "authentication", "authentication_error": "authentication", "permission_denied": "permission",
         "insufficient_quota": "quota", "insufficient_balance": "quota", "model_not_found": "model_not_found", "model_not_exist": "model_not_found",
         "context_length_exceeded": "context_length", "unsupported_parameter": "parameter", "unsupported_value": "parameter", "rate_limit_exceeded": "rate_limit"}
REJECTED_HTTP = {400, 401, 402, 403, 404, 413, 422, 429}


def model_failure(error: Exception, *, streamed=False) -> dict:
    current, seen = error, set()
    result = {"category": "unknown", "http_status": None, "parameter": None, "response_rejected": False}
    for _ in range(10):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))
        status = getattr(current, "status_code", None)
        if type(status) is not int:
            status = getattr(getattr(current, "response", None), "status_code", None)
        if type(status) is int and 400 <= status <= 599:
            body = getattr(current, "body", None)
            if isinstance(body, dict) and isinstance(body.get("error"), dict):
                body = body["error"]
            body = body if isinstance(body, dict) else {}
            code = body.get("code") or body.get("type")
            parameter = body.get("param")
            category = CODES.get(code) if isinstance(code, str) else None
            category = category or {400: "parameter", 401: "authentication", 402: "quota", 403: "permission", 404: "not_found",
                                    408: "timeout", 413: "request_too_large", 422: "parameter", 429: "rate_limit", 504: "timeout"}.get(status, "service" if status >= 500 else "request")
            return {"category": category, "http_status": status, "parameter": parameter if isinstance(parameter, str) and parameter in PARAMETERS else None,
                    "response_rejected": status in REJECTED_HTTP and not streamed}
        if isinstance(current, (APITimeoutError, httpx.TimeoutException, TimeoutError)):
            result["category"] = "timeout"
        elif isinstance(current, (APIConnectionError, httpx.ConnectError)) and result["category"] != "timeout":
            result["category"] = "connection"
        current = current.__cause__ or (current.__context__ if not current.__suppress_context__ else None)
    return result


def configuration_failure(error) -> dict:
    # Read exception text only to select fixed categories; never persist it.
    text = str(error).lower()
    category = "configuration"
    if "credential" in text or "api_key" in text or "api key" in text:
        category = "credentials_missing"
    elif "reasoning effort" in text:
        category = "reasoning"
    return {"category": category, "http_status": None, "parameter": None, "response_rejected": False}


@dataclass(slots=True)
class DiagnosticLlmClient(VvLlmClient):
    on_failure: Callable | None = None

    def complete(self, request):
        return self.complete_with_stream(request)

    def complete_with_stream(self, request, stream_callback=None):
        streamed = False

        def observe(event):
            nonlocal streamed
            streamed = True
            if stream_callback is not None:
                stream_callback(event)

        try:
            return VvLlmClient.complete_with_stream(self, request, observe)
        except Exception as error:
            if self.on_failure is not None:
                try:
                    self.on_failure(request, model_failure(error, streamed=streamed))
                except Exception:
                    # A failed diagnostic write must not replace the provider's original failure.
                    pass
            raise


def enrich_failures(timeline, events, failures, turn_id, unconfirmed_count):
    latest = {}
    rejected_operations = set()
    uncertain_operations = set()
    for event in events:
        if event["kind"] == "model_failure":
            diagnosis = failures.get(event.get("call_id"))
            latest[event["turn_id"]] = diagnosis
            if event["turn_id"] == turn_id and event.get("outcome") == "ambiguous":
                operation = event["operation_id"]
                if diagnosis and diagnosis["response_rejected"] and operation not in uncertain_operations:
                    rejected_operations.add(operation)
                else:
                    rejected_operations.discard(operation)
                    uncertain_operations.add(operation)
        elif event["kind"] == "model_success":
            latest.pop(event["turn_id"], None)
            rejected_operations.discard(event["operation_id"])
            uncertain_operations.add(event["operation_id"])
    for item in timeline:
        if item["kind"] == "error" and item.get("text") == "model_outcome_unknown":
            item["model_failure"] = latest.get(item["turn_id"]) or {"category": "unknown", "http_status": None, "parameter": None, "response_rejected": False}
    # Only suppress the generic warning if every unresolved operation is an observed model rejection.
    return unconfirmed_count > 0 and len(rejected_operations) == unconfirmed_count
