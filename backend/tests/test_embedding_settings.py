from __future__ import annotations

from typing import Any

import pytest

import utilities.ai_utils.embeddings as embeddings_module
from utilities.config.settings import normalize_embedding_backends


def _base_llm_settings() -> dict[str, Any]:
    return {
        "VERSION": "2",
        "endpoints": [
            {
                "id": "openai-default",
                "api_base": "https://api.openai.com/v1",
                "api_key": "",
            }
        ],
        "backends": {},
    }


def test_normalize_embedding_backends_migrates_legacy_text_embeddings_inference() -> None:
    data = {
        "llm_settings": _base_llm_settings(),
        "embedding_models": {
            "text_embeddings_inference": {
                "api_base": "http://localhost:8088/custom/embed",
                "api_key": "tei-secret",
            }
        },
    }

    changed = normalize_embedding_backends(data)

    assert changed is True
    assert "embedding_models" not in data
    embedding_backends = data["llm_settings"]["embedding_backends"]
    assert "openai" in embedding_backends
    assert "custom" in embedding_backends

    tei_endpoint = next(
        endpoint for endpoint in data["llm_settings"]["endpoints"] if endpoint.get("id") == "tei-default"
    )
    assert tei_endpoint["api_base"] == "http://localhost:8088/custom"
    assert tei_endpoint["api_key"] == "tei-secret"

    tei_model = embedding_backends["custom"]["models"]["text-embeddings-inference"]
    assert tei_model["request_mapping"]["path"] == "/embed"
    assert tei_model["response_mapping"]["data_path"] == "$[*]"


def test_normalize_embedding_backends_keeps_defaults_when_embedding_backends_missing() -> None:
    data = {
        "llm_settings": _base_llm_settings(),
    }

    changed = normalize_embedding_backends(data)

    assert changed is True
    openai_models = data["llm_settings"]["embedding_backends"]["openai"]["models"]
    assert list(openai_models) == [
        "text-embedding-3-large",
        "text-embedding-3-small",
        "text-embedding-ada-002",
    ]


def test_embedding_client_maps_legacy_provider_to_vv_llm_custom_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, Any] = {}

    class _FakeClient:
        def embed(self, text: str, *, dimensions: int | None = None) -> list[float]:
            recorded["embed"] = {"text": text, "dimensions": dimensions}
            return [0.1, 0.2]

        def embed_batch(self, texts: list[str], *, dimensions: int | None = None) -> list[list[float]]:
            recorded["embed_batch"] = {"texts": texts, "dimensions": dimensions}
            return [[1.0], [2.0]]

    class _FakeSettings:
        def get(self, key: str, default: Any = None) -> Any:
            if key == "llm_settings":
                return {
                    **_base_llm_settings(),
                    "embedding_backends": {
                        "custom": {
                            "models": {
                                "text-embeddings-inference": {
                                    "id": "text-embeddings-inference",
                                    "endpoints": ["tei-default"],
                                    "protocol": "custom_json_http",
                                    "request_mapping": {
                                        "method": "POST",
                                        "path": "/embed",
                                        "body_template": {"inputs": "${inputs}"},
                                    },
                                    "response_mapping": {"data_path": "$[*]"},
                                }
                            }
                        }
                    },
                }
            return default

    def _fake_create_embedding_client(*, backend: str, model: str | None, settings: Any, **_: Any) -> _FakeClient:
        recorded["create"] = {
            "backend": backend,
            "model": model,
            "settings_version": settings.VERSION,
        }
        return _FakeClient()

    monkeypatch.setattr(embeddings_module, "Settings", _FakeSettings)
    monkeypatch.setattr(embeddings_module, "create_embedding_client", _fake_create_embedding_client)

    client = embeddings_module.EmbeddingClient("text-embeddings-inference", "ignored-model", dimensions=768)

    assert recorded["create"] == {
        "backend": "custom",
        "model": "text-embeddings-inference",
        "settings_version": "2",
    }
    assert client.get("hello") == [0.1, 0.2]
    assert recorded["embed"] == {"text": "hello", "dimensions": 768}
    assert client.get(["a", "b"]) == [[1.0], [2.0]]
    assert recorded["embed_batch"] == {"texts": ["a", "b"], "dimensions": 768}
