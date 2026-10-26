from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


@pytest.fixture
def endpoint_server():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.server.received.append({"path": self.path, "body": body,
                                         "headers": {key.lower(): value for key, value in self.headers.items()}})
            if self.server.barrier is not None:
                self.server.barrier.wait(timeout=10)
            if self.server.error_message:
                status = 400
                response = {"error": {"message": self.server.error_message, "type": "invalid_request_error"}}
            elif self.path.endswith("/messages"):
                status = 200
                response = {"id": "loopback-message", "type": "message", "role": "assistant", "model": body["model"],
                            "content": [{"type": "thinking", "thinking": "native reasoning", "signature": "test"},
                                        {"type": "text", "text": "native reply"}],
                            "stop_reason": "end_turn", "stop_sequence": None,
                            "usage": {"input_tokens": 1, "output_tokens": 1}}
            else:
                status = 200
                response = {"id": "loopback-completion", "object": "chat.completion", "created": 0,
                            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                                "message": {"role": "assistant", "content": "reply:" + body["model"],
                                            "reasoning_content": "reason:" + body["messages"][-1]["content"]}}],
                            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
            encoded = json.dumps(response).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.received = []
    server.barrier = None
    server.error_message = ""
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_concurrent_real_draft_requests_do_not_read_or_mutate_saved_settings(endpoint_server, monkeypatch):
    from api.user_api import SettingAPI
    from models import Setting, create_tables
    from utilities.config import DEFAULT_SETTINGS
    from vv_llm.settings import settings as global_settings

    server, base = endpoint_server
    server.barrier = threading.Barrier(2)
    monkeypatch.setenv("OPENAI_API_KEY", "host-key-must-not-be-used")
    monkeypatch.setenv("OPENAI_ADMIN_KEY", "host-admin-must-not-be-used")
    monkeypatch.setenv("OPENAI_ORG_ID", "host-org-must-not-be-used")
    monkeypatch.setenv("OPENAI_PROJECT_ID", "host-project-must-not-be-used")
    monkeypatch.setenv("OPENAI_CUSTOM_HEADERS", "X-Host-Secret: host-header-must-not-be-used")
    monkeypatch.setenv("OPENAI_BASE_URL", base + "/host-config-must-not-be-used")
    monkeypatch.setenv("HTTP_PROXY", base + "/host-proxy-must-not-be-used")
    monkeypatch.setenv("HTTPS_PROXY", base + "/host-proxy-must-not-be-used")
    monkeypatch.setenv("NO_PROXY", "")
    create_tables()
    saved = Setting.create(data=deepcopy(DEFAULT_SETTINGS))
    saved_snapshot = deepcopy(saved.data)
    global_snapshot = deepcopy(global_settings.export())

    def reject_global_load(*args, **kwargs):
        raise AssertionError("Draft test must not load global vv_llm settings")

    monkeypatch.setattr(type(global_settings), "load", reject_global_load)
    payloads = [
        {"backend": "openai", "endpoint": {"id": "same-draft-id", "api_base": base + "/alpha/v1",
                                            "api_key": "alpha-draft-key", "headers": {"X-Draft": "alpha"}},
         "model_id": "draft-model-alpha", "message": "自定义测试消息"},
        {"backend": "openai", "endpoint": {"id": "same-draft-id", "api_base": base + "/beta/v1",
                                            "api_key": "", "headers": {"X-Draft": "beta"}},
         "model_id": "draft-model-beta"},
    ]
    originals = deepcopy(payloads)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(SettingAPI().test_model_endpoint, payloads))
        assert [response["status"] for response in responses] == [200, 200], responses
        assert responses[0]["data"] == {"content": "reply:draft-model-alpha", "reasoning_content": "reason:自定义测试消息"}
        assert responses[1]["data"] == {"content": "reply:draft-model-beta", "reasoning_content": "reason:Hi!"}
        requests = {item["path"]: item for item in server.received}
        assert set(requests) == {"/alpha/v1/chat/completions", "/beta/v1/chat/completions"}
        for name, message in (("alpha", "自定义测试消息"), ("beta", "Hi!")):
            request = requests[f"/{name}/v1/chat/completions"]
            assert request["body"]["model"] == f"draft-model-{name}"
            assert request["body"]["messages"] == [{"role": "user", "content": message}]
            assert request["body"]["stream"] is False
            assert request["headers"]["x-draft"] == name
        assert requests["/alpha/v1/chat/completions"]["headers"]["authorization"] == "Bearer alpha-draft-key"
        assert "authorization" not in requests["/beta/v1/chat/completions"]["headers"]
        assert "must-not-be-used" not in json.dumps(server.received)
        assert Setting.get_by_id(saved.id).data == saved_snapshot
        assert global_settings.export() == global_snapshot
        assert payloads == originals
    finally:
        saved.delete_instance()


def test_real_http_proxy_provider_error_is_redacted_without_retry(endpoint_server):
    from api.user_api import SettingAPI

    server, _ = endpoint_server
    secrets = ["synthetic-api-key", "synthetic-header-value", "synthetic-private-key", "synthetic-proxy-password"]
    server.error_message = "Invalid model; supplied credentials " + " ".join(secrets)
    payload = {"backend": "openai", "endpoint": {
        "id": "proxy-draft", "api_base": "http://draft-endpoint.invalid/v1", "api_key": secrets[0],
        "headers": {"X-Custom-Auth": secrets[1]}, "credentials": {"nested": {"private_key": secrets[2]}},
        "proxy": f"http://proxy-user:{secrets[3]}@127.0.0.1:{server.server_port}",
    }, "model_id": "invalid-draft-model", "message": "Hi"}
    result = SettingAPI().test_model_endpoint(payload)
    assert result["status"] == 502
    assert "Invalid model" in result["msg"]
    for secret in secrets:
        assert secret not in json.dumps(result)
    assert len(server.received) == 1
    assert server.received[0]["path"] == "http://draft-endpoint.invalid/v1/chat/completions"
    assert server.received[0]["headers"]["x-custom-auth"] == secrets[1]
    assert server.received[0]["headers"]["proxy-authorization"].startswith("Basic ")


def test_native_anthropic_real_request_uses_draft_key_and_correct_path(endpoint_server, monkeypatch):
    from api.user_api import SettingAPI

    server, base = endpoint_server
    monkeypatch.setenv("ANTHROPIC_API_KEY", "native-host-key-must-not-be-used")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "native-host-token-must-not-be-used")
    monkeypatch.setenv("ANTHROPIC_CUSTOM_HEADERS", "X-Host-Secret: native-host-header-must-not-be-used")
    result = SettingAPI().test_model_endpoint({
        "backend": "anthropic", "endpoint": {"id": "native-draft", "endpoint_type": "anthropic",
            "api_base": base + "/v1", "api_key": "native-draft-key"},
        "model_id": "native-draft-model", "message": "native custom message",
    })
    assert result["status"] == 200, result
    assert result["data"] == {"content": "native reply", "reasoning_content": "native reasoning"}
    assert len(server.received) == 1
    request = server.received[0]
    assert request["path"] == "/v1/messages"
    assert request["body"]["model"] == "native-draft-model"
    assert request["body"]["messages"] == [{"role": "user", "content": "native custom message"}]
    assert request["headers"]["x-api-key"] == "native-draft-key"
    assert "must-not-be-used" not in json.dumps(server.received)
