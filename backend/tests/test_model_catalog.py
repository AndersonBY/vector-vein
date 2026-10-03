from __future__ import annotations

import json
from copy import deepcopy

import pytest
from peewee import SqliteDatabase
from vv_llm.chat_clients import create_chat_client
from vv_llm.settings import Settings as VvLlmSettings
from vv_llm.types import BackendType, NOT_GIVEN

from utilities.config.model_catalog import CHAT_CATALOG, is_retired_model
from utilities.config.settings import (
    DEFAULT_SETTINGS,
    Settings,
    update_llm_settings_to_v2,
)
from worker.tasks.llms.universal_llm import UniversalLLMTask


def test_default_catalog_covers_current_providers_and_binds_every_model() -> None:
    llm = DEFAULT_SETTINGS["llm_settings"]
    endpoints = {endpoint["id"] for endpoint in llm["endpoints"]}
    for provider, catalog_backend in CHAT_CATALOG["backends"].items():
        backend = llm["backends"][provider]
        expected = {name for name in catalog_backend["models"] if not is_retired_model(provider, name)}
        assert {name for name, model in backend["models"].items() if model["enabled"]} == expected
        assert backend["default_model"] in expected
        for name, model in backend["models"].items():
            assert model["endpoints"]
            assert set(model["endpoints"]) <= endpoints
            if name in expected:
                assert model["context_length"] == catalog_backend["models"][name]["context_length"]
    assert "gpt-6.1-sol" in llm["backends"]["openai"]["models"]
    assert "glm-5.3" in llm["backends"]["zhipuai"]["models"]
    assert "kimi-k3" in llm["backends"]["moonshot"]["models"]
    assert "mimo-v2-pro" in llm["backends"]["xiaomi"]["models"]
    json.dumps(DEFAULT_SETTINGS)


def test_upgrade_retires_builtins_preserves_custom_routing_and_refreshes_capabilities() -> None:
    data = {
        "settings_version": 2,
        "agent": {"auto_title_model": ["OpenAI", "gpt-4o-mini"]},
        "llm_settings": {
            "VERSION": "2",
            "endpoints": [
                {
                    "id": "private",
                    "api_base": "https://example.invalid/v1",
                    "api_key": "test-key",
                }
            ],
            "backends": {
                "openai": {
                    "default_endpoint": "private",
                    "models": {
                        "gpt-4o-mini": {"id": "gpt-4o-mini", "endpoints": ["private"]},
                        "gpt-5.5": {
                            "id": "deployment-55",
                            "endpoints": [
                                {
                                    "endpoint_id": "private",
                                    "enabled": False,
                                    "priority": 2,
                                }
                            ],
                            "enabled": False,
                            "native_multimodal": False,
                            "context_length": 1024,
                        },
                        "gpt-4-custom": {
                            "id": "private-model",
                            "endpoints": ["private"],
                            "context_length": 8192,
                        },
                    },
                },
                "minimax": {"models": {"abab6-chat": {"id": "abab6-chat"}}},
                "xiaomi": {"default_endpoint": None, "models": {"mimo-v2-pro": {"id": "mimo-v2-pro", "endpoints": []}}},
            },
        },
    }
    update_llm_settings_to_v2(data)
    llm = data["llm_settings"]
    models = llm["backends"]["openai"]["models"]
    assert "gpt-4o-mini" not in models
    assert "abab6-chat" not in llm["backends"]["minimax"]["models"]
    assert models["gpt-5.5"]["id"] == "deployment-55"
    assert models["gpt-5.5"]["endpoints"] == [{"endpoint_id": "private", "enabled": False, "priority": 2}]
    assert models["gpt-5.5"]["enabled"] is False
    assert models["gpt-5.5"]["native_multimodal"] is True
    assert models["gpt-5.5"]["context_length"] == CHAT_CATALOG["backends"]["openai"]["models"]["gpt-5.5"]["context_length"]
    assert models["gpt-4-custom"]["context_length"] == 8192
    assert models["gpt-6.1-sol"]["endpoints"] == ["private"]
    assert llm["backends"]["xiaomi"]["models"]["mimo-v2-pro"]["endpoints"] == ["xiaomi-default"]
    assert llm["endpoints"][0]["api_key"] == "test-key"
    assert data["agent"]["auto_title_model"] == ["OpenAI", "gpt-5-nano"]
    previous = deepcopy(data)
    update_llm_settings_to_v2(data)
    assert data == previous
    json.dumps(data)


@pytest.mark.parametrize("version", [1, 2])
def test_legacy_settings_upgrade_without_removed_vv_llm_api(version: int) -> None:
    data = {"settings_version": version}
    if version == 1:
        data.update({"openai_api_type": "open_ai", "openai_api_key": "test-key"})
    else:
        data["llm_settings"] = {
            "VERSION": "1",
            "openai": {"default_endpoint": "openai-default", "models": {}},
        }
    update_llm_settings_to_v2(data)
    assert data["llm_settings"]["VERSION"] == "2"
    assert "openai" not in data["llm_settings"]
    assert "gpt-6.1-sol" in data["llm_settings"]["backends"]["openai"]["models"]
    endpoints = data["llm_settings"]["endpoints"]
    assert len(endpoints) == len({endpoint["id"] for endpoint in endpoints})
    if version == 1:
        assert next(endpoint for endpoint in endpoints if endpoint["id"] == "openai-default")["api_key"] == "test-key"


def test_settings_persists_catalog_upgrade_and_remains_stable() -> None:
    from models import Setting, User

    database = SqliteDatabase(":memory:")
    with database.bind_ctx([Setting, User]):
        database.create_tables([User, Setting])
        row = Setting.create(
            data={
                "settings_version": 2,
                "llm_settings": {"VERSION": "2", "backends": {}, "endpoints": []},
            }
        )
        loaded = Settings()
        assert "xiaomi" in loaded.llm_settings["backends"]
        assert row.get_by_id(row.id).data == loaded.data
        assert Settings().data == loaded.data


@pytest.mark.parametrize(
    "provider,model",
    [
        ("OpenAI", "gpt-6.1-sol"),
        ("Qwen", "qwen3-next-80b-a3b-thinking"),
        ("Qwen", "qwen3-vl-235b-a22b-thinking"),
        ("Xiaomi", "mimo-v2-pro"),
    ],
)
def test_workflow_uses_catalog_ids_and_sampling_parameters(monkeypatch: pytest.MonkeyPatch, provider: str, model: str) -> None:
    import httpx2
    import worker.tasks.llms.base_llm as llm_module

    llm = deepcopy(DEFAULT_SETTINGS["llm_settings"])
    for endpoint in llm["endpoints"]:
        endpoint["api_key"] = "test-key"
    monkeypatch.setattr(
        llm_module,
        "Settings",
        lambda: type("TestSettings", (), {"llm_settings": llm})(),
    )
    http_client = httpx2.Client(transport=httpx2.MockTransport(lambda _: httpx2.Response(200)))
    monkeypatch.setattr(llm_module, "new_llm_http_client", lambda **_: http_client)
    values = {
        "model_provider": provider,
        "llm_model": model,
        "prompt": "hello",
        "temperature": 0.7,
        "top_p": 0.9,
        "stream": True,
    }
    workflow = {
        "nodes": [
            {
                "id": "node",
                "type": "UniversalLlm",
                "category": "llms",
                "data": {"template": {key: {"value": value} for key, value in values.items()}},
            }
        ],
        "edges": [],
    }
    task = UniversalLLMTask(workflow, "node")
    assert task.model == model
    assert task.model_settings.endpoints
    if provider == "OpenAI":
        assert task.temperature is NOT_GIVEN
        assert task.top_p is NOT_GIVEN
        assert task.stream is True
    # Constructing the SDK catches incompatible httpx/httpx2 clients without a live request.
    assert task.chat_client.raw_client
    http_client.close()


def test_llm_http_client_uses_current_sdk_and_respects_proxy_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    import httpx2
    import utilities.network.llm_client as network

    monkeypatch.setattr(
        network,
        "Settings",
        lambda: type("TestSettings", (), {"get": lambda self, key, default: default})(),
    )
    monkeypatch.setattr(network, "proxies_for_requests", lambda: {})
    settings = VvLlmSettings(**DEFAULT_SETTINGS["llm_settings"])
    settings.get_endpoint("openai-default").api_key = "test-key"
    with network.new_llm_http_client() as client:
        assert isinstance(client, httpx2.Client)
        assert client.trust_env is False
        assert create_chat_client(
            backend=BackendType.OpenAI,
            model="gpt-6.1-sol",
            http_client=client,
            settings=settings,
        ).raw_client
    client = network.new_llm_http_client(is_async=True)
    assert isinstance(client, httpx2.AsyncClient)
    asyncio.run(client.aclose())


@pytest.mark.parametrize("model", ["whisper-1", "tts-1", "tts-1-hd", "dall-e-3"])
def test_openai_media_sdk_routing_survives_chat_catalog_retirement(monkeypatch: pytest.MonkeyPatch, model: str) -> None:
    import utilities.ai_utils.client as clients

    data = deepcopy(DEFAULT_SETTINGS)
    data["llm_settings"]["endpoints"].append({"id": "media", "api_base": "https://example.invalid/v1", "api_key": "test-key"})
    data["llm_settings"]["backends"]["openai"]["models"][model] = {"id": "media-deployment", "endpoints": ["media"], "enabled": True}
    update_llm_settings_to_v2(data)
    binding = data["llm_settings"]["backends"]["openai"]["models"][model]
    assert binding["enabled"] is False
    monkeypatch.setattr(clients, "Settings", lambda: type("TestSettings", (), {"get": lambda self, key: data[key]})())
    client, model_id = clients.get_openai_client_and_model_id(model_id=model)
    assert model_id == "media-deployment"
    assert str(client.base_url) == "https://example.invalid/v1/"
    client.close()
