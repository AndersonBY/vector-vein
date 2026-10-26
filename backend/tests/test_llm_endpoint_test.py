from copy import deepcopy
import json

import httpx2
import pytest
from vv_llm.settings import settings as global_settings

from utilities import llm_endpoint_test as probe


def draft(**updates):
    return {"backend": "local", "endpoint": {"id": "draft", "api_base": "https://draft.invalid/v1"},
            "model_id": "chosen-model", "message": "hello", **updates}


def capture_transport(monkeypatch, response_body=None, status=200):
    captured = []

    def send(client, request, **kwargs):
        captured.append((client, request))
        return httpx2.Response(status, request=request, json=response_body or {
            "id": "test", "object": "chat.completion", "created": 0, "model": "chosen-model",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": "worked", "reasoning_content": "thought"}}],
        })

    monkeypatch.setattr(httpx2.Client, "send", send)
    return captured


@pytest.mark.parametrize("backend", ["local", "_local__private-family", "openai", "qwen"])
def test_actual_client_uses_only_submitted_draft(monkeypatch, backend):
    captured = capture_transport(monkeypatch)
    for key in ["OPENAI_API_KEY", "OPENAI_ADMIN_KEY", "OPENAI_ORG_ID", "OPENAI_PROJECT_ID"]:
        monkeypatch.setenv(key, "ambient-secret")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://wrong.invalid")
    monkeypatch.setenv("OPENAI_CUSTOM_HEADERS", "Authorization: Bearer ambient-secret\nX-Ambient: ambient-secret")
    payload = draft(backend=backend)
    payload["endpoint"]["headers"] = {"X-Draft": "submitted", "X-Model": "${model_id}"}
    original = deepcopy(payload)
    saved = global_settings.export()
    monkeypatch.setattr(type(global_settings), "load", lambda *_: pytest.fail("global settings modified"))
    result = probe.run_model_endpoint_test(payload)
    assert result == {"content": "worked", "reasoning_content": "thought"}
    assert payload == original
    assert global_settings.export() == saved
    assert len(captured) == 1
    client, request = captured[0]
    assert str(request.url) == "https://draft.invalid/v1/chat/completions"
    body = json.loads(request.content)
    assert body == {"model": "chosen-model", "messages": [{"role": "user", "content": "hello"}],
                    "stream": False, "max_tokens": 2048}
    assert request.headers["X-Draft"] == "submitted"
    assert request.headers["X-Model"] == "chosen-model"
    assert "ambient-secret" not in str(request.headers)
    assert "authorization" not in request.headers
    assert all(value == 20 for value in request.extensions["timeout"].values())
    assert client.trust_env is False
    assert client.is_closed


@pytest.mark.parametrize("updates", [
    {"backend": "unknown"}, {"backend": None}, {"endpoint": None},
    {"endpoint": {"id": "", "api_base": "https://draft.invalid"}},
    {"endpoint": {"id": "draft"}},
    {"endpoint": {"id": "draft", "api_base": "file:///tmp/no"}},
    {"endpoint": {"id": "draft", "api_base": "https://draft.invalid:bad"}},
    {"model_id": " "}, {"model_id": 1}, {"message": " "}, {"message": None}, {"message": "x" * 8001},
])
def test_invalid_input_never_reaches_transport(monkeypatch, updates):
    captured = capture_transport(monkeypatch)
    with pytest.raises(ValueError):
        probe.run_model_endpoint_test(draft(**updates))
    assert not captured


@pytest.mark.parametrize("adapter,backend", [
    ("anthropic", "anthropic"), ("openai_azure", "openai"),
    ("openai_vertex", "openai"), ("anthropic_vertex", "anthropic"),
    ("anthropic_bedrock", "anthropic"),
])
def test_native_credentials_must_be_explicit(monkeypatch, adapter, backend):
    captured = capture_transport(monkeypatch)
    for key in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AZURE_OPENAI_API_KEY", "AWS_ACCESS_KEY_ID"]:
        monkeypatch.setenv(key, "ambient-secret")
    payload = draft(backend=backend)
    payload["endpoint"].update(endpoint_type=adapter, credentials={})
    with pytest.raises(ValueError):
        probe.run_model_endpoint_test(payload)
    assert not captured


def test_defaults_message_and_reasoning_model_token_budget(monkeypatch):
    captured = capture_transport(monkeypatch)
    payload = draft(model_id="gpt-6-test")
    del payload["message"]
    probe.run_model_endpoint_test(payload)
    body = json.loads(captured[0][1].content)
    assert body["messages"][0]["content"] == "Hi!"
    assert body["max_completion_tokens"] == 2048
    assert "max_tokens" not in body


def test_error_redaction_does_not_read_saved_settings(monkeypatch):
    from api.user_api import SettingAPI
    import utilities.config

    payload = draft()
    payload["endpoint"].update(api_key="key-secret", access_token="token-secret", proxy="http://user:proxy-secret@proxy.invalid",
                               headers={"X-Custom": "header-secret"}, credentials={"nested": {"value": "nested-secret"}})
    def fail(_):
        raise RuntimeError("key-secret token-secret proxy-secret header-secret nested-secret " + "x" * 2000)

    monkeypatch.setattr("api.user_api.run_model_endpoint_test", fail)
    monkeypatch.setattr(utilities.config, "Settings", lambda: pytest.fail("saved settings read"))
    result = SettingAPI().test_model_endpoint(payload)
    assert result["status"] == 502
    assert len(result["msg"]) <= 1500
    assert not any(secret in result["msg"] for secret in ["key-secret", "token-secret", "proxy-secret", "header-secret", "nested-secret"])


def test_provider_error_has_no_retry(monkeypatch):
    captured = capture_transport(monkeypatch, {"error": {"message": "unavailable"}}, 503)
    with pytest.raises(Exception):
        probe.run_model_endpoint_test(draft())
    assert len(captured) == 1


def test_model_listing_errors_redact_supplied_credentials(monkeypatch):
    from api.user_api import SettingAPI
    from vv_llm.types import EndpointSetting

    def fail(_):
        raise RuntimeError("provider key-secret url-password " + "x" * 2000)

    monkeypatch.setattr(EndpointSetting, "model_list", fail)
    result = SettingAPI().list_models({"api_key": "key-secret", "base_url": "https://user:url-password@draft.invalid"})
    assert result["status"] == 500
    assert "key-secret" not in result["msg"]
    assert "url-password" not in result["msg"]
    assert len(result["msg"]) <= 1500


def test_transport_timeout_returns_safe_error_and_closes_client(monkeypatch):
    from api.user_api import SettingAPI

    clients = []
    def send(client, request, **kwargs):
        clients.append(client)
        assert max(request.extensions["timeout"].values()) == 20
        raise httpx2.ReadTimeout("Timed out", request=request)

    monkeypatch.setattr(httpx2.Client, "send", send)
    result = SettingAPI().test_model_endpoint(draft())
    assert result["status"] == 502
    assert len(clients) == 1
    assert clients[0].is_closed


def test_native_anthropic_uses_explicit_key_and_extracts_only_text(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ambient-secret")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "ambient-token")
    captured = capture_transport(monkeypatch, {
        "id": "message", "type": "message", "role": "assistant", "model": "chosen-model",
        "content": [{"type": "thinking", "thinking": "thought", "signature": "unused"},
                    {"type": "text", "text": "worked"}],
        "stop_reason": "end_turn", "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 2},
    })
    payload = draft(backend="anthropic")
    payload["endpoint"].update(api_key="draft-key", endpoint_type="anthropic")
    assert probe.run_model_endpoint_test(payload) == {"content": "worked", "reasoning_content": "thought"}
    request = captured[0][1]
    assert request.headers["x-api-key"] == "draft-key"
    assert "ambient" not in str(request.headers)
    assert str(request.url) == "https://draft.invalid/v1/messages"


def test_bedrock_ignores_host_bearer_token(monkeypatch):
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "ambient-secret")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "ambient-token")
    captured = capture_transport(monkeypatch, {
        "id": "message", "type": "message", "role": "assistant", "model": "chosen-model",
        "content": [{"type": "text", "text": "worked"}], "stop_reason": "end_turn",
        "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 2},
    })
    payload = draft(backend="anthropic")
    payload["endpoint"].update(endpoint_type="anthropic_bedrock", region="us-east-1",
                               credentials={"access_key": "draft-access", "secret_key": "draft-secret"})
    assert probe.run_model_endpoint_test(payload) == {"content": "worked"}
    request = captured[0][1]
    assert "draft-access" in request.headers["Authorization"]
    assert "ambient" not in str(request.headers)


def test_pydantic_error_never_exposes_nested_credentials(monkeypatch):
    from api.user_api import SettingAPI

    captured = capture_transport(monkeypatch)
    payload = draft()
    payload["endpoint"]["api_key"] = {"nested": "validation-secret"}
    result = SettingAPI().test_model_endpoint(payload)
    assert result["status"] == 400
    assert "validation-secret" not in result["msg"]
    assert not captured


def test_responses_api_preserves_selected_endpoint_headers_and_timeout(monkeypatch):
    captured = capture_transport(monkeypatch, {
        "id": "response", "object": "response", "created_at": 0, "model": "chosen-model", "status": "completed",
        "output": [{"id": "message", "type": "message", "status": "completed", "role": "assistant", "content": [
            {"type": "output_text", "text": "worked", "annotations": []}]}],
        "parallel_tool_calls": False, "tool_choice": "auto", "tools": [],
    })
    payload = draft()
    payload["endpoint"].update(response_api=True, headers={"X-Draft": "submitted"})
    assert probe.run_model_endpoint_test(payload) == {"content": "worked"}
    request = captured[0][1]
    assert str(request.url) == "https://draft.invalid/v1/responses"
    assert request.headers["X-Draft"] == "submitted"
    assert json.loads(request.content)["max_output_tokens"] == 2048
    assert all(value == 20 for value in request.extensions["timeout"].values())


def test_vertex_uses_only_explicit_current_token(monkeypatch):
    import time
    import vv_llm.utilities.gcp_token as tokens

    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "ambient-secret.json")
    monkeypatch.setattr(tokens, "_refresh_user_token_with_expiry", lambda *_: pytest.fail("token refreshed"))
    captured = capture_transport(monkeypatch)
    payload = draft(backend="openai")
    payload["endpoint"].update(endpoint_type="openai_vertex", region="us-central1", access_token="draft-token",
                               access_token_expires_at=time.time() + 3600, credentials={"quota_project_id": "draft-project"})
    assert probe.run_model_endpoint_test(payload)["content"] == "worked"
    assert captured[0][1].headers["Authorization"] == "Bearer draft-token"
