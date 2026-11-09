from copy import copy
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError, APIStatusError
from vv_agent.llm.vv_llm_client import VvLlmClient

from task_agent.model_errors import DiagnosticLlmClient, configuration_failure, enrich_failures, model_failure


def http_error(status, body=None):
    response = httpx.Response(status, request=httpx.Request("POST", "https://endpoint.invalid/v1"))
    return APIStatusError("SECRET_PROVIDER_BODY", response=response, body=body)


@pytest.mark.parametrize(("status", "category"), [(401,"authentication"),(402,"quota"),(403,"permission"),(404,"not_found"),(422,"parameter"),(429,"rate_limit"),(500,"service"),(504,"timeout")])
def test_http_failures_keep_only_allowlisted_facts(status, category):
    cause = http_error(status, {"error": {"message": "SECRET_PROVIDER_BODY", "code": "SECRET_CODE", "param": "SECRET_PARAM"}})
    wrapped = RuntimeError("All endpoints failed: SECRET_KEY")
    wrapped.__cause__ = cause
    failure = model_failure(wrapped)
    assert failure["category"] == category and failure["http_status"] == status
    assert failure["parameter"] is None
    assert "SECRET" not in repr(failure)
    assert failure["response_rejected"] == (status in {401,402,403,404,422,429})


def test_quota_model_and_parameter_errors_use_known_provider_codes():
    assert model_failure(http_error(429, {"code":"insufficient_quota"}))["category"] == "quota"
    assert model_failure(http_error(404, {"error":{"code":"model_not_found"}}))["category"] == "model_not_found"
    assert model_failure(http_error(400, {"code":"unsupported_parameter","param":"reasoning_effort"}))["parameter"] == "reasoning_effort"
    assert not model_failure(http_error(401), streamed=True)["response_rejected"]


def test_timeout_and_connection_causes_are_not_misreported_as_bad_keys():
    request = httpx.Request("POST", "https://endpoint.invalid")
    assert model_failure(APITimeoutError(request))["category"] == "timeout"
    assert model_failure(APIConnectionError(request=request))["category"] == "connection"
    assert model_failure(RuntimeError("unrecognized failure"))["category"] == "unknown"
    assert configuration_failure(ValueError("An endpoint credential is no longer available"))["category"] == "credentials_missing"


def test_client_copy_captures_failure_without_changing_exception_or_streaming(monkeypatch):
    records, streamed = [], []
    error = http_error(401)
    def fail(self, request, callback):
        raise error
    monkeypatch.setattr(VvLlmClient, "complete_with_stream", fail)
    client = copy(DiagnosticLlmClient(endpoint_targets=[], on_failure=lambda request, failure: records.append(failure)))
    with pytest.raises(APIStatusError) as raised:
        client.complete(SimpleNamespace(metadata={"call_id":"op/1"}))
    assert raised.value is error
    assert records[-1]["category"] == "authentication"
    def partial(self, request, callback):
        callback({"delta":"text"})
        raise error
    monkeypatch.setattr(VvLlmClient, "complete_with_stream", partial)
    with pytest.raises(APIStatusError):
        client.complete_with_stream(SimpleNamespace(), streamed.append)
    assert streamed == [{"delta":"text"}]
    assert records[-1]["response_rejected"] is False
    def broken_sink(*args):
        raise OSError("diagnostic storage unavailable")
    client.on_failure = broken_sink
    with pytest.raises(APIStatusError) as raised:
        client.complete(SimpleNamespace())
    assert raised.value is error


def test_projection_does_not_hide_unresolved_tools_or_unknown_model_attempts():
    event = {"kind":"model_failure","turn_id":"turn","call_id":"op/1","operation_id":"op","outcome":"ambiguous"}
    failure = model_failure(http_error(401))
    timeline = [{"kind":"error","turn_id":"turn","text":"model_outcome_unknown"}]
    assert enrich_failures(timeline, [event], {"op/1":failure}, "turn", 1)
    assert timeline[0]["model_failure"]["category"] == "authentication"
    assert not enrich_failures(timeline, [event], {"op/1":failure}, "turn", 2)
    later = {**event,"call_id":"op/2"}
    assert not enrich_failures(timeline, [event,later], {"op/1":failure}, "turn", 1)
    success = {**event,"kind":"model_success"}
    assert not enrich_failures(timeline, [event,success], {"op/1":failure}, "turn", 1)
    old = [{"kind":"error","turn_id":"old","text":"model_outcome_unknown"}]
    assert not enrich_failures(old, [], {}, "old", 1)
    assert old[0]["model_failure"]["category"] == "unknown"
