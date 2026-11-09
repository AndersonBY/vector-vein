from copy import deepcopy
import json

import httpx2
import pytest
from vv_llm.settings import settings as global_settings

from api import user_api
from utilities import retrieval_model_test as probe
from test_external_settings_ui import external_settings  # noqa: F401


def draft(kind="embedding"):
    model = {"id": "configured-id", "enabled": False, "endpoints": ["wrong-endpoint"]}
    if kind == "embedding":
        model.update(protocol="openai_embeddings", dimensions=3)
    else:
        model.update(protocol="custom_json_http", request_mapping={
            "path": "/v1/rerank", "body_template": {"model": "${model_id}", "query": "${query}",
                                                    "documents": "${documents}", "top_n": "${top_n}"}},
            response_mapping={"results_path": "$.results[*]", "field_map": {
                "index": "$.index", "relevance_score": "$.relevance_score"}})
    return {"kind": kind, "backend": "local", "model_key": "chosen", "model_config": model,
            "endpoint": {"id": "draft", "api_base": "https://draft.invalid/v1" if kind == "embedding"
                         else "https://draft.invalid", "enabled": False},
            "binding": {"endpoint_id": "draft", "model_id": "deployed-id", "enabled": False}}


def body(kind="embedding"):
    if kind == "embedding":
        return {"data": [{"index": 0, "embedding": [.1, .2, .3]}, {"index": 1, "embedding": [.4, .5, .6]}]}
    return {"results": [{"index": 1, "relevance_score": .9, "document": "DO-NOT-RETURN"},
                        {"index": 0, "relevance_score": .2}]}


def transport(monkeypatch, value=None, status=200, error=None):
    calls = []

    def send(client, request, **kwargs):
        calls.append((client, request))
        if error:
            raise error("SECRET-KEY server failure", request=request)
        return httpx2.Response(status, request=request, content=json.dumps(value).encode(),
                               headers={"content-type": "application/json"})

    monkeypatch.setattr(httpx2.Client, "send", send)
    return calls


@pytest.mark.parametrize("kind", ["embedding", "rerank"])
def test_real_vv_client_uses_selected_binding_and_no_ambient_state(monkeypatch, kind):
    calls = transport(monkeypatch, body(kind))
    for key in ["OPENAI_API_KEY", "COHERE_API_KEY", "JINA_API_KEY", "VOYAGE_API_KEY", "HTTP_PROXY", "HTTPS_PROXY",
                "ALL_PROXY", "OPENAI_CUSTOM_HEADERS"]:
        monkeypatch.setenv(key, "AMBIENT-SECRET")
    payload = draft(kind)
    payload.update(input="ignored", documents=["ignored"], query="ignored")
    payload["endpoint"]["headers"] = {"X-Model": "${model_id}", "X-Draft": "draft-header"}
    original, saved = deepcopy(payload), global_settings.export()
    monkeypatch.setattr(type(global_settings), "load", lambda *args: pytest.fail("Global settings mutated"))
    monkeypatch.setattr(user_api, "Settings", lambda: pytest.fail("Saved settings read without reference"))
    result = user_api.SettingAPI().test_retrieval_model(payload)
    assert result["status"] == 200
    assert result["data"]["kind"] == kind
    assert result["data"]["count"] == 2
    assert result["data"]["elapsed_ms"] >= 0
    assert len(calls) == 1
    client, request = calls[0]
    assert client.is_closed and client.trust_env is False
    assert all(value == 20 for value in request.extensions["timeout"].values())
    assert "AMBIENT" not in str(request.headers)
    assert "authorization" not in request.headers
    assert request.headers["X-Model"] == "deployed-id"
    sent = json.loads(request.content)
    assert sent["model"] == "deployed-id"
    assert sent["input" if kind == "embedding" else "documents"] == list(probe.TEST_TEXTS)
    assert str(request.url) == "https://draft.invalid/v1/" + ("embeddings" if kind == "embedding" else "rerank")
    if kind == "embedding":
        assert result["data"]["dimensions"] == 3
        assert set(result["data"]) == {"kind", "elapsed_ms", "dimensions", "count"}
    else:
        assert sent["query"] == probe.TEST_QUERY and sent["top_n"] == 2
        assert result["data"]["results"] == [{"index": 1, "score": .9}, {"index": 0, "score": .2}]
        assert "DO-NOT-RETURN" not in str(result)
    assert payload == original and global_settings.export() == saved


@pytest.mark.parametrize("kind", ["embedding", "rerank"])
def test_custom_request_and_response_mappings_are_applied(monkeypatch, kind):
    payload = draft(kind)
    payload["endpoint"]["api_base"] = "https://draft.invalid"
    payload["binding"] = "draft"
    payload["model_config"].update(protocol="custom_json_http", request_mapping={
        "path": "/custom", "headers": {"X-Mapping": "explicit"},
        "body_template": {"deployment": "${model_id}", "texts": "${inputs}" if kind == "embedding" else "${documents}"}},
        response_mapping={"data_path" if kind == "embedding" else "results_path": "$.answer[*]", "field_map": {
            "index": "position", "embedding" if kind == "embedding" else "relevance_score": "value"}})
    calls = transport(monkeypatch, {"answer": [{"position": 1, "value": [.1, .2, .3] if kind == "embedding" else .9},
                                             {"position": 0, "value": [.4, .5, .6] if kind == "embedding" else .1}]})
    result = user_api.SettingAPI().test_retrieval_model(payload)
    assert result["status"] == 200
    assert str(calls[0][1].url) == "https://draft.invalid/custom"
    expected = {"deployment": "configured-id", "texts": list(probe.TEST_TEXTS)}
    if kind == "embedding":
        expected["dimensions"] = 3
    assert json.loads(calls[0][1].content) == expected
    assert calls[0][1].headers["X-Mapping"] == "explicit"


@pytest.mark.parametrize("kind", ["embedding", "rerank"])
def test_cohere_native_protocol(monkeypatch, kind):
    payload = draft(kind)
    payload["backend"] = "cohere"
    payload["endpoint"].update(api_base="https://draft.invalid", api_key="SYNTHETIC-KEY")
    payload["model_config"]["protocol"] = "cohere_embed_v2" if kind == "embedding" else "cohere_rerank_v2"
    value = {"embeddings": {"float": [[.1, .2, .3], [.4, .5, .6]]}} if kind == "embedding" else body(kind)
    calls = transport(monkeypatch, value)
    assert user_api.SettingAPI().test_retrieval_model(payload)["status"] == 200
    assert calls[0][1].headers["Authorization"] == "Bearer SYNTHETIC-KEY"
    assert str(calls[0][1].url) == "https://draft.invalid/v2/" + ("embed" if kind == "embedding" else "rerank")


@pytest.mark.parametrize("change", ["kind", "backend", "key", "model", "endpoint", "binding", "mismatch", "override",
                                  "url", "absolute_mapping", "disabled_vertex", "protocol", "oversize"])
def test_invalid_config_does_not_send(monkeypatch, change):
    calls = transport(monkeypatch, body())
    payload = draft()
    if change in {"kind", "backend"}:
        payload[change] = "invalid"
    elif change == "key":
        payload["model_key"] = " "
    elif change == "model":
        payload["model_config"] = {"id": {"secret": "SECRET-KEY"}}
    elif change == "endpoint":
        payload["endpoint"] = None
    elif change == "binding":
        payload["binding"] = None
    elif change == "mismatch":
        payload["binding"] = "other-endpoint"
    elif change == "override":
        payload["binding"]["model_id"] = " "
    elif change == "url":
        payload["endpoint"]["api_base"] = "http://localhost:bad"
    elif change == "absolute_mapping":
        payload["model_config"]["request_mapping"] = {"path": "https://other.invalid/steal"}
    elif change == "disabled_vertex":
        payload["endpoint"]["endpoint_type"] = "openai_vertex"
    elif change == "protocol":
        payload["model_config"]["protocol"] = "llama_rerank"
    else:
        payload["input"] = "x" * 65537
    result = user_api.SettingAPI().test_retrieval_model(payload)
    assert result["status"] == 400 and result["data"]["error_code"] == "invalid_config"
    assert "SECRET" not in str(result)
    assert not calls


@pytest.mark.parametrize("status,code", [(401, "auth_failed"), (403, "auth_failed"), (404, "not_found"),
                                        (429, "request_failed"), (503, "request_failed"), (302, "request_failed")])
@pytest.mark.parametrize("kind", ["embedding", "rerank"])
def test_http_failures_are_safe_and_never_retried(monkeypatch, kind, status, code):
    calls = transport(monkeypatch, {"error": "SECRET-KEY"}, status)
    payload = draft(kind)
    payload["endpoint"]["api_key"] = "SECRET-KEY"
    result = user_api.SettingAPI().test_retrieval_model(payload)
    assert result["status"] == 502 and result["data"]["error_code"] == code
    assert "SECRET" not in str(result)
    assert len(calls) == 1 and calls[0][0].is_closed


@pytest.mark.parametrize("error,code", [(httpx2.ReadTimeout, "timeout"), (httpx2.ConnectTimeout, "timeout"),
                                       (httpx2.ConnectError, "connection_failed"), (httpx2.ProxyError, "connection_failed"),
                                       (httpx2.ReadError, "request_failed")])
def test_transport_failure_classification_no_retry(monkeypatch, error, code):
    calls = transport(monkeypatch, error=error)
    result = user_api.SettingAPI().test_retrieval_model(draft())
    assert result["status"] == 502 and result["data"]["error_code"] == code
    assert "SECRET" not in str(result)
    assert len(calls) == 1 and calls[0][0].is_closed


@pytest.mark.parametrize("value", [
    {}, {"data": []}, {"data": [{"index": 0, "embedding": [.1, .2, .3]}]},
    {"data": [{"index": 0, "embedding": []}, {"index": 1, "embedding": []}]},
    {"data": [{"index": 0, "embedding": [1, 2]}, {"index": 1, "embedding": [1, 2, 3]}]},
    {"data": [{"index": 0, "embedding": [1, 2]}, {"index": 1, "embedding": [1, 2]}]},
    {"data": [{"index": 0, "embedding": [float("nan"), 2, 3]}, {"index": 1, "embedding": [1, 2, 3]}]},
    {"data": [{"index": 0, "embedding": [float("inf"), 2, 3]}, {"index": 1, "embedding": [1, 2, 3]}]},
    {"data": [{"index": 0, "embedding": [1, 2, 3]}, {"index": 0, "embedding": [1, 2, 3]}]},
])
def test_embedding_success_requires_valid_vectors(monkeypatch, value):
    calls = transport(monkeypatch, value)
    result = user_api.SettingAPI().test_retrieval_model(draft())
    assert result["status"] == 502 and result["data"]["error_code"] == "invalid_response"
    assert len(calls) == 1


@pytest.mark.parametrize("index,score", [(-1, .9), (2, .9), (0, .9), (True, .9), (.5, .9), ("1", .9),
                                        (1, float("nan")), (1, float("inf")), (1, "SECRET-KEY")])
def test_rerank_success_requires_strict_indices_and_scores(monkeypatch, index, score):
    transport(monkeypatch, {"results": [{"index": index, "relevance_score": score}, {"index": 0, "relevance_score": .1}]})
    result = user_api.SettingAPI().test_retrieval_model(draft("rerank"))
    assert result["status"] == 502 and result["data"]["error_code"] == "invalid_response"
    assert "SECRET" not in str(result)


@pytest.mark.parametrize("kind", ["embedding", "rerank"])
def test_credentials_roundtrip_does_not_persist_or_modify_settings(external_settings, monkeypatch, kind):  # noqa: F811
    from models import Setting
    api_module, setting, path, external = external_settings
    api = api_module.SettingAPI()
    endpoint = api.get({})["data"]["data"]["llm_settings"]["endpoints"][0]
    payload = draft(kind)
    payload["endpoint"] = endpoint
    payload["binding"] = "external"
    original = deepcopy(payload)
    saved = deepcopy(Setting.get_by_id(setting.id).data)
    contents = path.read_bytes()
    calls = transport(monkeypatch, body(kind))
    result = api.test_retrieval_model(payload)
    assert result["status"] == 200
    assert calls[0][1].headers["Authorization"] == "Bearer SYNTHETIC-EXTERNAL-KEY"
    assert "SYNTHETIC" not in str(result)
    assert payload == original and path.read_bytes() == contents
    assert Setting.get_by_id(setting.id).data == saved
    payload["endpoint"]["api_base"] = "https://different.invalid"
    assert api.test_retrieval_model(payload)["data"]["error_code"] == "invalid_config"
    assert len(calls) == 1


def test_empty_rerank_is_invalid_and_partial_valid_rerank_reports_actual_count(monkeypatch):
    transport(monkeypatch, {"results": []})
    assert user_api.SettingAPI().test_retrieval_model(draft("rerank"))["data"]["error_code"] == "invalid_response"
    transport(monkeypatch, {"results": [{"index": 1, "relevance_score": .9}]})
    result = user_api.SettingAPI().test_retrieval_model(draft("rerank"))
    assert result["status"] == 200 and result["data"]["count"] == 1


def test_json_parse_failure_is_invalid_response(monkeypatch):
    def send(client, request, **kwargs):
        return httpx2.Response(200, request=request, content=b"SECRET-KEY not JSON")
    monkeypatch.setattr(httpx2.Client, "send", send)
    result = user_api.SettingAPI().test_retrieval_model(draft())
    assert result["status"] == 502 and result["data"]["error_code"] == "invalid_response"
    assert "SECRET" not in str(result)


def test_parallel_probes_have_independent_clients_and_retry_behavior(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from vv_llm.retrieval_clients import common
    original_retry = common.request_json_with_retry
    barrier = threading.Barrier(2)
    calls = []

    def send(client, request, **kwargs):
        calls.append((client, request))
        barrier.wait(timeout=5)
        status = 503 if request.headers.get("authorization") == "Bearer first" else 200
        return httpx2.Response(status, request=request, json=body())

    monkeypatch.setattr(httpx2.Client, "send", send)
    first, second = draft(), draft()
    first["endpoint"]["api_key"] = "first"
    second["endpoint"]["api_key"] = "second"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(user_api.SettingAPI().test_retrieval_model, [first, second]))
    assert [result["status"] for result in results] == [502, 200]
    assert len(calls) == 2 and calls[0][0] is not calls[1][0]
    assert all(client.is_closed for client, _ in calls)
    assert common.request_json_with_retry is original_retry


def test_explicit_cached_vertex_token_never_refreshes_or_reads_ambient(monkeypatch):
    import time
    import vv_llm.embedding_clients.base_client as native
    original = native.get_token_with_cache
    token_calls = []

    def token(**kwargs):
        token_calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(native, "get_token_with_cache", token)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "must-not-read.json")
    payload = draft()
    payload["endpoint"].update(endpoint_type="openai_vertex", credentials={"explicit": True},
                               access_token="synthetic-token", access_token_expires_at=time.time() + 3600)
    calls = transport(monkeypatch, body())
    assert user_api.SettingAPI().test_retrieval_model(payload)["status"] == 200
    assert len(token_calls) == len(calls) == 1
    assert calls[0][1].headers["Authorization"] == "Bearer synthetic-token"
