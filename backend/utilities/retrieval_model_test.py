"""Bounded retrieval probes using only the selected model and endpoint drafts."""
from copy import deepcopy
import json
import math
import time
from typing import cast
from urllib.parse import urlsplit

import httpx2
from vv_llm.embedding_clients import EmbeddingClient, create_embedding_client
from vv_llm.rerank_clients import create_rerank_client
from vv_llm.retrieval_clients.common import render_template
from vv_llm.settings import Settings as LlmSettings
from vv_llm.types.enums import EmbeddingBackendType, RerankBackendType
from vv_llm.types.llm_parameters import EndpointSetting, RetrievalModelSetting

from utilities.ai_utils.rerank import Reranker


REQUEST_TIMEOUT = 20.0
TEST_TEXTS = ("An apple is a fruit.", "A bicycle has two wheels.")
TEST_QUERY = "Which document describes fruit?"
_MESSAGES = {
    "invalid_config": "Invalid retrieval model configuration. Check the selected model, endpoint and mappings.",
    "auth_failed": "Authentication failed. Check the selected endpoint credentials.",
    "not_found": "The retrieval endpoint or model was not found. Check the URL, protocol and model ID.",
    "timeout": "The retrieval request timed out. Check the endpoint and retry.",
    "connection_failed": "Could not connect to the retrieval endpoint. Check its address and proxy.",
    "invalid_response": "The endpoint returned invalid retrieval results. Check the protocol, mappings and dimensions.",
    "request_failed": "The retrieval request failed. Check the endpoint and model configuration.",
}


class RetrievalTestError(Exception):
    def __init__(self, code):
        self.code = code
        self.status = 400 if code == "invalid_config" else 502
        super().__init__(_MESSAGES[code])


def transport_error(error):
    if isinstance(error, httpx2.TimeoutException):
        return RetrievalTestError("timeout")
    if isinstance(error, (httpx2.ConnectError, httpx2.ProxyError)):
        return RetrievalTestError("connection_failed")
    if isinstance(error, httpx2.HTTPStatusError):
        code = {401: "auth_failed", 403: "auth_failed", 404: "not_found"}.get(error.response.status_code, "request_failed")
        return RetrievalTestError(code)
    return RetrievalTestError("request_failed")


class _SingleRequestClient(httpx2.Client):
    attempted = False

    def request(self, *args, **kwargs):
        if self.attempted:
            raise RetrievalTestError("request_failed")
        self.attempted = True
        try:
            response = super().request(*args, **kwargs)
            # Fail before vv-llm's status/connection retry loop can retry this draft.
            response.raise_for_status()
            return response
        except httpx2.HTTPError as error:
            raise transport_error(error) from None


def _settings(payload):
    if not isinstance(payload, dict) or len(json.dumps(payload)) > 65536:
        raise ValueError("Invalid probe payload")
    kind = payload.get("kind")
    if kind not in {"embedding", "rerank"}:
        raise ValueError("Invalid kind")
    enum = EmbeddingBackendType if kind == "embedding" else RerankBackendType
    backend = enum(payload.get("backend")).value
    key = payload.get("model_key")
    if not isinstance(key, str) or not key.strip():
        raise ValueError("Missing model key")
    endpoint = EndpointSetting.model_validate(deepcopy(payload.get("endpoint")))
    model = RetrievalModelSetting.model_validate(deepcopy(payload.get("model_config")))
    if not endpoint.id.strip() or not model.id.strip():
        raise ValueError("Missing model or endpoint ID")
    url = urlsplit(endpoint.api_base or "")
    if (url.scheme not in {"http", "https"} or not url.hostname or url.port == 0
            or url.username or url.password or url.query or url.fragment):
        raise ValueError("Invalid endpoint URL")
    binding = deepcopy(payload.get("binding"))
    if isinstance(binding, str):
        binding_id = binding
    elif isinstance(binding, dict):
        binding_id = binding.get("endpoint_id")
        override = binding.get("model_id")
        if override is not None and (not isinstance(override, str) or not override.strip()):
            raise ValueError("Invalid model override")
        if override is None:
            binding.pop("model_id", None)
        binding["enabled"] = True
    else:
        raise ValueError("Select an endpoint binding")
    if binding_id != endpoint.id:
        raise ValueError("Binding does not match selected endpoint")
    if model.dimensions is not None and not 1 <= model.dimensions <= 65536:
        raise ValueError("Invalid dimensions")
    if model.request_mapping:
        path = model.request_mapping.path
        if not path.startswith("/") or path.startswith("//") or urlsplit(path).scheme:
            raise ValueError("Mapping must use a path on the selected endpoint")
    endpoint.enabled = model.enabled = True
    model.endpoints = [binding]
    settings = LlmSettings(endpoints=[endpoint.model_dump()], rate_limit={"enabled": False}, **{
        f"{kind}_backends": {backend: {"models": {key: model.model_dump()}, "default_endpoint": endpoint.id}}})
    endpoint = settings.get_endpoint(endpoint.id)
    if (endpoint.endpoint_type or "").startswith("anthropic"):
        raise ValueError("Unsupported retrieval endpoint adapter")
    if endpoint.endpoint_type == "openai_vertex":
        expiry = endpoint.access_token_expires_at
        if not (endpoint.credentials and endpoint.access_token and expiry and math.isfinite(expiry)
                and expiry > time.time() + 300 + REQUEST_TIMEOUT):
            raise ValueError("Vertex requires explicit credentials and a current token; probes do not refresh tokens")
    return kind, backend, key, settings, endpoint, model


def run_retrieval_model_test(payload):
    started = time.perf_counter()
    try:
        kind, backend, key, settings, endpoint, model = _settings(payload)
    except (ValueError, TypeError, OverflowError):
        raise RetrievalTestError("invalid_config") from None
    try:
        with _SingleRequestClient(proxy=endpoint.proxy, timeout=REQUEST_TIMEOUT, trust_env=False,
                                  follow_redirects=False) as http_client:
            factory = create_embedding_client if kind == "embedding" else create_rerank_client
            client = factory(backend=backend, model=key, random_endpoint=False, endpoint_id=endpoint.id,
                             settings=settings, http_client=http_client)
            http_client.headers.update(render_template(endpoint.headers or {}, {
                "model": key, "model_id": client.model_id, "endpoint_id": endpoint.id,
            }))
            try:
                if kind == "embedding":
                    response = cast(EmbeddingClient, client).create_embeddings(input=list(TEST_TEXTS), dimensions=model.dimensions,
                                                        timeout=REQUEST_TIMEOUT)
                    vectors = [item.embedding for item in response.data]
                    dimensions = len(vectors[0]) if vectors else 0
                    if (len(vectors) != 2 or not dimensions or {item.index for item in response.data} != {0, 1}
                            or any(len(vector) != dimensions or any(not math.isfinite(value) for value in vector)
                                   for vector in vectors)
                            or (model.dimensions is not None and dimensions != model.dimensions)):
                        raise RetrievalTestError("invalid_response")
                    result = {"kind": kind, "dimensions": dimensions, "count": len(vectors)}
                else:
                    response = Reranker(client).rerank(query=TEST_QUERY, documents=list(TEST_TEXTS), top_n=2,
                                                       return_documents=False, timeout=REQUEST_TIMEOUT)
                    result = {"kind": kind, "count": len(response.results), "results": [
                        {"index": item.index, "score": item.relevance_score} for item in response.results]}
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
                raise RetrievalTestError("invalid_response" if http_client.attempted else "invalid_config") from None
            result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
            return result
    except RetrievalTestError:
        raise
    except (ValueError, TypeError):
        raise RetrievalTestError("invalid_config") from None
    except Exception as error:
        raise transport_error(error) from None
