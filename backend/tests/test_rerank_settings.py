from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from utilities.config.settings import (
    DEFAULT_RERANK_BACKENDS, DEFAULT_SETTINGS, Settings, normalize_rerank_backends,
    update_llm_settings_to_v2, validate_rerank_settings,
)
from utilities.ai_utils import rerank


def configured(provider="custom"):
    return {
        "settings_version": 2,
        "knowledge_retrieval": {"rerank": {"provider": provider, "model": "chosen"}},
        "llm_settings": {
            "VERSION": "2", "backends": {},
            "endpoints": [{"id": "rerank", "api_base": "http://127.0.0.1:8012", "api_key": ""}],
            "rerank_backends": {provider: {"default_endpoint": "rerank", "models": {
                "chosen": {"id": "local-reranker", "protocol": "custom_json_http",
                           "request_mapping": {"method": "POST", "path": "/v1/rerank", "body_template": {
                               "model": "${model_id}", "query": "${query}", "documents": "${documents}",
                               "top_n": "${top_n}"}},
                           "response_mapping": {"results_path": "$.results[*]", "field_map": {
                               "index": "$.index", "relevance_score": "$.relevance_score"}}}
            }}},
        },
    }


@pytest.mark.parametrize("provider", DEFAULT_RERANK_BACKENDS)
def test_native_provider_settings_and_model_key_survive_normalization(provider):
    data = configured(provider)
    update_llm_settings_to_v2(data)
    assert validate_rerank_settings(data) == (provider, "chosen")
    model = data["llm_settings"]["rerank_backends"][provider]["models"]["chosen"]
    assert model["id"] == "local-reranker"
    assert model["response_mapping"]["field_map"]["index"] == "$.index"


def test_disabled_by_default_and_external_model_file_is_not_rewritten(tmp_path, monkeypatch):
    assert validate_rerank_settings(DEFAULT_SETTINGS) == ("", "")
    raw = configured()["llm_settings"]
    raw["rerank_backends"]["custom"]["models"]["chosen"]["enabled"] = False
    path = tmp_path / "models.json"
    original = json.dumps(raw)
    path.write_text(original, encoding="utf-8")
    monkeypatch.setenv("VECTORVEIN_LLM_SETTINGS_FILE", str(path))
    monkeypatch.setattr(Settings, "load_setting", lambda self: setattr(self, "data", {}))
    loaded = Settings().data
    assert set(DEFAULT_RERANK_BACKENDS) <= set(loaded["llm_settings"]["rerank_backends"])
    assert loaded["llm_settings"]["rerank_backends"]["custom"]["models"]["chosen"]["enabled"] is False
    assert path.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("change", [
    "missing", "disabled", "missing_endpoint", "disabled_endpoint", "disabled_binding",
    "bad_url", "bad_port", "bad_host", "partial", "wrong_model_key",
])
def test_selection_rejects_invalid_model_or_endpoint(change):
    data = configured()
    backend = data["llm_settings"]["rerank_backends"]["custom"]
    model = backend["models"]["chosen"]
    endpoint = data["llm_settings"]["endpoints"][0]
    if change == "missing":
        backend["models"].clear()
    elif change == "disabled":
        model["enabled"] = False
    elif change == "missing_endpoint":
        backend["default_endpoint"] = "missing"
    elif change == "disabled_endpoint":
        endpoint["enabled"] = False
    elif change == "disabled_binding":
        model["endpoints"] = [{"endpoint_id": "rerank", "enabled": False}]
    elif change == "bad_url":
        endpoint["api_base"] = "file:///tmp/rerank"
    elif change == "bad_port":
        endpoint["api_base"] = "http://localhost:invalid"
    elif change == "bad_host":
        endpoint["api_base"] = "http://["
    elif change == "partial":
        data["knowledge_retrieval"]["rerank"]["provider"] = ""
    else:
        data["knowledge_retrieval"]["rerank"]["model"] = "local-reranker"
    with pytest.raises(ValueError):
        validate_rerank_settings(data)


def test_normalization_preserves_disabled_models():
    data = configured()
    data["llm_settings"]["rerank_backends"]["custom"]["models"]["chosen"]["enabled"] = False
    before = deepcopy(data)
    normalize_rerank_backends(data)
    assert data["llm_settings"]["rerank_backends"]["custom"] == before["llm_settings"]["rerank_backends"]["custom"]


def test_real_vv_client_vekai_mapping_without_network(monkeypatch):
    from vv_llm.rerank_clients.base_client import RerankClient
    from vv_llm.settings import Settings as LlmSettings
    data = configured()
    monkeypatch.setattr(rerank, "Settings", lambda: SimpleNamespace(data=data, get=data.get))
    requests = []

    def request(client, **kwargs):
        requests.append(kwargs)
        return {"model": "local-reranker", "object": "list", "usage": {"total_tokens": 20},
                "results": [{"index": 1, "relevance_score": .6627}, {"index": 0, "relevance_score": .3082}]}

    monkeypatch.setattr(RerankClient, "_request_json", request)
    worker = rerank.configured_reranker()
    response = worker.rerank(query="apple", documents=["banana", "apple"], top_n=2, return_documents=False)
    assert [item.index for item in response.results] == [1, 0]
    assert requests[0]["path"] == "/v1/rerank"
    assert requests[0]["body"] == {
        "model": "local-reranker", "query": "apple", "documents": ["banana", "apple"], "top_n": 2}
    assert isinstance(worker.client.settings, LlmSettings)


def test_disabled_selection_never_constructs_provider(monkeypatch):
    data = deepcopy(DEFAULT_SETTINGS)
    monkeypatch.setattr(rerank, "Settings", lambda: SimpleNamespace(data=data, get=data.get))
    monkeypatch.setattr(rerank, "create_rerank_client", lambda **kwargs: pytest.fail("Provider should stay disabled"))
    assert rerank.configured_reranker() is None


@pytest.mark.parametrize("provider,path", [
    ("cohere", "/v2/rerank"), ("jina", "/v1/rerank"), ("voyage", "/rerank"), ("siliconflow", "/rerank"),
])
def test_native_protocol_and_endpoint_model_override(monkeypatch, provider, path):
    from vv_llm.rerank_clients.base_client import RerankClient
    data = configured(provider)
    model = data["llm_settings"]["rerank_backends"][provider]["models"]["chosen"]
    model.pop("protocol")
    model.pop("request_mapping")
    model.pop("response_mapping")
    model["endpoints"] = [{"endpoint_id": "rerank", "model_id": "deployed-reranker"}]
    monkeypatch.setattr(rerank, "Settings", lambda: SimpleNamespace(data=data, get=data.get))

    def request(client, **kwargs):
        assert kwargs["path"] == path
        assert kwargs["body"]["model"] == "deployed-reranker"
        item = {"index": 0, "relevance_score": .9, "document": {"text": "forged"}}
        return {"data" if provider == "voyage" else "results": [item],
                "meta": {"billed_units": {"search_units": 1}, "tokens": {"input_tokens": 1}}}

    monkeypatch.setattr(RerankClient, "_request_json", request)
    assert rerank.configured_reranker().rerank(query="apple", documents=["apple"]).results[0].index == 0


@pytest.mark.parametrize("item", [
    {"index": True, "relevance_score": .9}, {"index": 0.7, "relevance_score": .9},
    {"index": "0", "relevance_score": .9}, {"relevance_score": .9},
    {"index": 0}, {"index": 0, "relevance_score": "0.9"},
    {"index": 0, "relevance_score": float("nan")},
])
def test_raw_response_cannot_hide_invalid_fields_through_vv_coercion(monkeypatch, item):
    from vv_llm.rerank_clients.base_client import RerankClient
    data = configured()
    monkeypatch.setattr(rerank, "Settings", lambda: SimpleNamespace(data=data, get=data.get))
    monkeypatch.setattr(RerankClient, "_request_json", lambda *args, **kwargs: {"results": [item]})
    with pytest.raises(ValueError):
        rerank.configured_reranker().rerank(query="apple", documents=["apple"])
