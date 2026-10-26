from types import SimpleNamespace

import pytest
from vv_llm.types import BackendType

from utilities.model_endpoints import available_workflow_endpoints, bind_workflow_endpoint
from worker.tasks.llms import base_llm
from worker.tasks.media_processing import base_vlm


def bindings():
    return [{"endpoint_id": "late", "priority": 3}, "legacy",
            {"endpoint_id": "tie", "model_id": "provider-alias", "rpm": 7},
            {"endpoint_id": "off", "priority": 1, "enabled": False},
            {"endpoint_id": "global-off", "priority": 1}]


def settings():
    return SimpleNamespace(get_endpoint=lambda key: SimpleNamespace(
        id=key, enabled=key != "global-off", endpoint_type=None))


def test_sdk_ordering_preserves_legacy_and_equal_priority_order():
    assert available_workflow_endpoints(settings(), bindings()) == ["legacy", bindings()[2], bindings()[0]]


@pytest.mark.parametrize("module,task_class,is_vlm", [
    (base_llm, base_llm.BaseLLMTask, False), (base_vlm, base_vlm.BaseVLMTask, True),
])
def test_workflow_tries_priority_order_and_applies_endpoint_binding(monkeypatch, module, task_class, is_vlm):
    task = task_class.__new__(task_class)
    task.MODEL_TYPE = BackendType.OpenAI
    task.model = "catalog-model"
    task.model_settings = SimpleNamespace(id="default-provider-model", max_output_tokens=32, endpoints=bindings())
    task.system_prompt = ""
    task.thinking = None
    task.temperature = 0.5
    task.stream = False
    task.multiple_input = False
    task.detail_type = "auto"
    task.prompts_count = 1
    task.endpoint_available = lambda _: True
    task.add_endpoint_request_record = lambda _: True
    monkeypatch.setattr(module, "vv_llm_settings", settings())
    client = SimpleNamespace(raw_client="cached-wrong-endpoint")
    monkeypatch.setattr(module, "create_chat_client", lambda **_: client)
    calls = []

    def complete(selected, *args):
        assert "raw_client" not in selected.__dict__
        calls.append((selected.endpoint.id, selected.model_id, selected.rpm))
        if len(calls) == 1:
            selected.raw_client = "cached-first-endpoint"
            raise RuntimeError("first provider unavailable")
        return SimpleNamespace(content="ok", reasoning_content=None,
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1), tool_calls=None)

    task._create_completion_response = complete
    result = task.process_prompt("hello", "image", 0) if is_vlm else task.process_prompt("hello", 0)
    assert result.content_output == "ok"
    assert calls == [("legacy", "default-provider-model", None), ("tie", "provider-alias", 7)]


def test_first_policy_selects_highest_priority_enabled_binding(monkeypatch):
    from vv_llm.types import ModelSetting
    from test_workflow_model_capabilities import workflow

    model = ModelSetting(id="custom", endpoints=bindings())
    selected_settings = settings()
    selected_settings.load = lambda _: None
    selected_settings.get_backend = lambda _: SimpleNamespace(models={"custom": model})
    monkeypatch.setattr(base_llm, "Settings", lambda: SimpleNamespace(llm_settings={}))
    monkeypatch.setattr(base_llm, "vv_llm_settings", selected_settings)
    monkeypatch.setattr(base_llm, "create_chat_client", lambda **_: SimpleNamespace())
    monkeypatch.setattr(base_llm, "new_llm_http_client", lambda **_: None)
    monkeypatch.setattr(base_llm.BaseLLMTask, "MODEL_TYPE", BackendType.OpenAI, raising=False)
    task = base_llm.BaseLLMTask(workflow(llm_model="custom", prompt="hello", temperature=0.5, endpoint_policy="first"), "node")
    assert task.model_settings.endpoints == ["legacy"]


def test_sdk_chat_selects_priority_and_provider_model_id_without_workflow_changes():
    import json
    from copy import deepcopy
    import httpx2
    from vv_llm.chat_clients import create_chat_client
    from vv_llm.types import ModelSetting
    from utilities.config.settings import DEFAULT_SETTINGS

    config = deepcopy(DEFAULT_SETTINGS["llm_settings"])
    endpoint = deepcopy(config["endpoints"][0])
    endpoints = []
    for name in ("late", "first", "equal"):
        endpoints.append({**endpoint, "id": name, "enabled": True, "api_key": "test-key",
                          "api_base": f"https://{name}.invalid/v1", "endpoint_type": "openai"})
    config["endpoints"] = endpoints
    config["backends"]["openai"]["models"] = {"custom": ModelSetting(
        id="default-model", endpoints=[{"endpoint_id": "late", "priority": 2},
            {"endpoint_id": "first", "priority": 1, "model_id": "provider-alias"},
            {"endpoint_id": "equal", "priority": 1}]).model_dump(mode="json")}
    config["backends"]["openai"]["default_model"] = "custom"
    captured = []

    def respond(request):
        captured.append((request.url.host, json.loads(request.content)["model"]))
        return httpx2.Response(200, json={"id": "test", "object": "chat.completion", "created": 0,
            "model": "provider-alias", "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"},
            "finish_reason": "stop"}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})

    with httpx2.Client(transport=httpx2.MockTransport(respond)) as http:
        client = create_chat_client(backend=BackendType.OpenAI, model="custom", settings=config, http_client=http)
        client.create_completion(messages=[{"role": "user", "content": "hello"}], max_tokens=10)
        original_backend = client.backend_settings
        bind_workflow_endpoint(client, client.settings.get_endpoint("equal"),
            {"endpoint_id": "equal", "model_id": "second-alias"}, "default-model")
        client.create_completion(messages=[{"role": "user", "content": "hello"}], max_tokens=10)
        bind_workflow_endpoint(client, client.settings.get_endpoint("equal"),
            {"endpoint_id": "equal", "model_id": "third-alias"}, "default-model")
        client.create_completion(messages=[{"role": "user", "content": "hello"}], max_tokens=10)
        assert original_backend.models["custom"].endpoints[2] == {"endpoint_id": "equal", "priority": 1}
    assert captured == [("first.invalid", "provider-alias"), ("equal.invalid", "second-alias"),
                        ("equal.invalid", "third-alias")]
