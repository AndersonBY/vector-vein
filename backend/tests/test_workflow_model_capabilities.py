from types import SimpleNamespace

import pytest
from vv_llm.types import BackendType, ModelSetting, NOT_GIVEN

from utilities.workflow_errors import WorkflowInputError
from utilities.model_capabilities import validate_workflow_model
from worker.tasks.llms import base_llm
from worker.tasks.media_processing import base_vlm


def workflow(**values):
    return {"nodes": [{"id": "node", "type": "Test", "category": "llms", "data": {
        "template": {key: {"value": value} for key, value in values.items()}
    }}], "edges": []}


@pytest.fixture
def configured(monkeypatch):
    model = ModelSetting(id="custom", context_length=100, max_output_tokens=40,
                         function_call_available=False, response_format_available=False, native_multimodal=False)
    backend = SimpleNamespace(models={"custom": model})
    settings = SimpleNamespace(load=lambda _: None, get_backend=lambda _: backend)
    for module in (base_llm, base_vlm):
        monkeypatch.setattr(module, "Settings", lambda: SimpleNamespace(llm_settings={"backends": {
            "openai": {"default_model": "custom"}}}))
        monkeypatch.setattr(module, "vv_llm_settings", settings)
    monkeypatch.setattr(base_llm.BaseLLMTask, "MODEL_TYPE", BackendType.OpenAI, raising=False)
    return model


@pytest.mark.parametrize("values,match", [
    ({"use_function_call": True, "functions": [{"name": "test"}]}, "function calling"),
    ({"response_format": "json_object"}, "JSON object"),
    ({"max_output_tokens": 41}, "configured model maximum"),
    ({"max_output_tokens": 101}, "model context"),
])
def test_llm_rejects_before_client_creation(monkeypatch, configured, values, match):
    def forbidden(**kwargs):
        pytest.fail("client I/O constructed before validation")
    monkeypatch.setattr(base_llm, "create_chat_client", forbidden)
    monkeypatch.setattr(base_llm, "new_llm_http_client", forbidden)
    with pytest.raises(WorkflowInputError, match=match):
        base_llm.BaseLLMTask(workflow(prompt="hello", temperature=0.5, **values), "node")


@pytest.mark.parametrize("values", [
    {}, {"use_function_call": True},
    {"use_function_call": True, "functions": [{"name": "test"}], "function_call_mode": "none"},
    {"output_schema": '{"type":"object"}'}, {"max_output_tokens": 40},
])
def test_llm_accepts_inactive_tools_schema_and_default_model(monkeypatch, configured, values):
    monkeypatch.setattr(base_llm, "create_chat_client", lambda **_: SimpleNamespace())
    monkeypatch.setattr(base_llm, "new_llm_http_client", lambda **_: None)
    task = base_llm.BaseLLMTask(workflow(prompt="hello", temperature=0.5, **values), "node")
    assert task.model == "custom"
    assert task.tools is NOT_GIVEN
    assert task.response_format is NOT_GIVEN
    assert task.model_settings.max_output_tokens == 40


@pytest.mark.parametrize("values,match", [
    ({"images": ["https://example.invalid/image.png"]}, "image input"),
    ({"response_format": "json_object"}, "JSON object"),
    ({"max_output_tokens": 41}, "configured model maximum"),
])
def test_vlm_rejects_before_image_io(monkeypatch, configured, values, match):
    def forbidden(**kwargs):
        pytest.fail("image processed before validation")
    monkeypatch.setattr(base_vlm, "ImageProcessor", forbidden)
    with pytest.raises(WorkflowInputError, match=match):
        base_vlm.BaseVLMTask(workflow(llm_model="custom", text_prompt="hello", images_or_urls="images", **values), "node")


def test_supported_capabilities_and_budget_preserve_configured_model(configured):
    supported = configured.model_copy(update={"function_call_available": True,
        "response_format_available": True, "native_multimodal": True})
    selected = validate_workflow_model(supported, tools=True, json_object=True, images=True, max_output_tokens=20)
    assert selected.max_output_tokens == 20
    assert supported.max_output_tokens == 40
    assert validate_workflow_model(supported) is supported


def test_supported_workflow_options_are_forwarded(monkeypatch, configured):
    configured.function_call_available = True
    configured.response_format_available = True
    configured.native_multimodal = True
    monkeypatch.setattr(base_llm, "create_chat_client", lambda **_: SimpleNamespace())
    monkeypatch.setattr(base_llm, "new_llm_http_client", lambda **_: None)
    task = base_llm.BaseLLMTask(workflow(prompt="hello", temperature=0.5, use_function_call=True,
        functions=[{"name": "test"}], response_format="json_object", max_output_tokens=20), "node")
    assert task.tools == [{"type": "function", "function": {"name": "test"}}]
    assert task.response_format == {"type": "json_object"}
    monkeypatch.setattr(base_vlm, "ImageProcessor", lambda **_: SimpleNamespace(data_url="data:image/png;base64,test"))
    vlm = base_vlm.BaseVLMTask(workflow(llm_model="custom", text_prompt="hello", images_or_urls="images",
        images=["image.png"], response_format="json_object", max_output_tokens=20), "node")
    assert vlm.response_format == {"type": "json_object"}
    assert vlm.model_settings.max_output_tokens == 20


@pytest.mark.parametrize("budget", [-1, "invalid", 101, 1.5, True])
def test_output_budget_without_configured_cap_still_checks_context(configured, budget):
    with pytest.raises(WorkflowInputError):
        validate_workflow_model(configured.model_copy(update={"max_output_tokens": None}), max_output_tokens=budget)
