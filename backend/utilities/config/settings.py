# @Author: Bi Ying
# @Date:   2024-04-29 16:50:17
from copy import deepcopy
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from vv_llm.settings import Settings as VvLlmSettings

from .model_catalog import CHAT_CATALOG, DEFAULT_CHAT_BACKENDS, OPENAI_SERVICE_MODELS, is_retired_model


DEFAULT_EMBEDDING_BACKENDS = {
    "openai": {
        "default_endpoint": "openai-default",
        "models": {
            "text-embedding-3-large": {
                "id": "text-embedding-3-large",
                "endpoints": ["openai-default"],
                "protocol": "openai_embeddings",
                "dimensions": 3072,
            },
            "text-embedding-3-small": {
                "id": "text-embedding-3-small",
                "endpoints": ["openai-default"],
                "protocol": "openai_embeddings",
                "dimensions": 1536,
            },
            "text-embedding-ada-002": {
                "id": "text-embedding-ada-002",
                "endpoints": ["openai-default"],
                "protocol": "openai_embeddings",
                "dimensions": 1536,
            },
        },
    },
    "cohere": {"models": {}},
    "jina": {"models": {}},
    "voyage": {"models": {}},
    "siliconflow": {"models": {}},
    "local": {"models": {}},
    "custom": {
        "default_endpoint": "tei-default",
        "models": {
            "text-embeddings-inference": {
                "id": "text-embeddings-inference",
                "endpoints": ["tei-default"],
                "protocol": "custom_json_http",
                "request_mapping": {
                    "method": "POST",
                    "path": "/embed",
                    "body_template": {
                        "inputs": "${inputs}",
                    },
                },
                "response_mapping": {
                    "data_path": "$[*]",
                },
            },
        },
    },
}


DEFAULT_SETTINGS = {
    "initial_setup": False,
    "settings_version": 2,
    "output_folder": "./",
    "data_path": "./data",
    "log_path": "./log",
    "email": {
        "user": "",
        "password": "",
        "smtp_host": "",
        "smtp_port": "",
        "smtp_ssl": True,
    },
    "pexels_api_key": "",
    "stable_diffusion_base_url": "http://127.0.0.1:7860",
    "stability_key": "",
    "use_system_proxy": True,
    "skip_ssl_verification": False,
    "website_domain": "vectorvein.ai",
    "agent": {
        "auto_title": True,
        "auto_title_model": ["OpenAI", "gpt-5-nano"],
        "screenshot_monitor_device": 0,
        "tool_call_data_generate_model": ["OpenAI", "gpt-5-nano"],
    },
    "microphone_device": 0,
    "shortcuts": {},
    "tts": {
        "piper": {"api_base": "http://localhost:5000"},
        "reecho": {"api_key": "", "voices": []},
        "azure": {"api_key": "", "service_region": "", "voices": []},
    },
    "asr": {
        "provider": "openai",
        "openai": {
            "same_as_llm": True,
            "api_base": "https://api.openai.com/v1",
            "api_key": "",
            "model": "whisper-1",
        },
    },
    "web_search": {
        "jinaai": {"api_key": ""},
        "bing": {
            "ocp_apim_subscription_key": "",
            "endpoint": "https://api.bing.microsoft.com/v7.0/search",
        },
    },
    "llm_settings": {
        "endpoints": [
            {
                "id": "openai-default",
                "api_base": "https://api.openai.com/v1",
                "api_key": "",
                "rpm": 900,
                "tpm": 150000,
            },
            {
                "id": "azure-openai",
                "region": "East US",
                "api_base": "",
                "api_key": "",
                "rpm": 900,
                "tpm": 150000,
                "is_azure": True,
            },
            {
                "id": "tei-default",
                "api_base": "http://localhost:8080",
                "api_key": "",
            },
            {
                "id": "anthropic-default",
                "api_base": "https://api.anthropic.com/v1",
                "api_key": "",
            },
            {
                "id": "moonshot-default",
                "api_base": "https://api.moonshot.cn/v1",
                "api_key": "",
                "rpm": 30,
                "tpm": 3000000,
                "concurrent_requests": 30,
            },
            {
                "id": "minimax-default",
                "api_base": "https://api.minimax.cn/v1",
                "api_key": "",
            },
            {
                "id": "gemini-default",
                "api_base": "https://generativelanguage.googleapis.com/v1beta/openai/",
                "api_key": "",
            },
            {
                "id": "deepseek-default",
                "api_base": "https://api.deepseek.com/v1",
                "api_key": "",
            },
            {
                "id": "groq-default",
                "api_base": "https://api.groq.com/openai/v1",
                "api_key": "",
            },
            {
                "id": "mistral-default",
                "api_base": "https://api.mistral.ai/v1",
                "api_key": "",
            },
            {
                "id": "lingyiwanwu-default",
                "api_base": "https://api.lingyiwanwu.com/v1",
                "api_key": "",
            },
            {
                "id": "zhipuai-default",
                "api_base": "https://open.bigmodel.cn/api/paas/v4",
                "api_key": "",
            },
            {
                "id": "qwen-default",
                "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "api_key": "",
                "rpm": 60,
                "tpm": 600000,
            },
            {
                "id": "baichuan-default",
                "api_base": "https://api.baichuan-ai.com/v1",
                "api_key": "",
            },
            {
                "id": "ernie-default",
                "api_base": "https://qianfan.baidubce.com/v2",
                "api_key": "",
            },
            {
                "id": "stepfun-default",
                "api_base": "https://api.stepfun.com/v1",
                "api_key": "",
            },
            {
                "id": "xai-default",
                "api_base": "https://api.x.ai/v1",
                "api_key": "",
            },
            {
                "id": "xiaomi-default",
                "api_base": "https://api.xiaomimimo.com/v1",
                "api_key": "",
            },
            {
                "api_base": "https://api.siliconflow.cn/v1",
                "api_key": "",
                "concurrent_requests": 20,
                "id": "siliconflow",
                "rpm": 1000,
                "tpm": 50000,
            },
        ],
        "backends": deepcopy(DEFAULT_CHAT_BACKENDS),
        "embedding_backends": deepcopy(DEFAULT_EMBEDDING_BACKENDS),
    },
    "custom_llms": {},
}


def deep_merge(default, custom):
    """
    Recursively merge two dictionaries. The values from `custom` will overwrite
    the values from `default` only if they are at the same depth.
    """
    for key, value in custom.items():
        if isinstance(value, Mapping) and key in default and isinstance(default[key], Mapping):
            default[key] = deep_merge(default[key], value)
        else:
            default[key] = value
    return default


def normalize_chat_backends(data: dict[str, Any]) -> None:
    normalize_embedding_backends(data)
    raw = deepcopy(data.get("llm_settings", {}))
    backends = raw.setdefault("backends", {})
    for provider in DEFAULT_CHAT_BACKENDS:
        # vv-llm 0.7 only accepts providers nested under backends.
        if provider in raw:
            backends[provider] = raw.pop(provider)
        backend = backends.setdefault(provider, {})
        default = DEFAULT_CHAT_BACKENDS[provider]
        if not backend.get("default_endpoint"):
            backend["default_endpoint"] = default.get("default_endpoint")
        models = backend.setdefault("models", {})
        for name in list(models):
            if is_retired_model(provider, name):
                del models[name]
        for name, model in default["models"].items():
            # Refresh built-in capabilities while retaining routing and enablement.
            overrides = {key: models.get(name, {})[key] for key in ("id", "endpoints", "enabled") if key in models.get(name, {})}
            models[name] = {**deepcopy(model), **overrides}
        if provider == "openai":
            for name in OPENAI_SERVICE_MODELS:
                models[name]["enabled"] = False

    endpoints = raw["endpoints"] = list({endpoint["id"]: endpoint for endpoint in raw.get("endpoints", [])}.values())
    endpoint_ids = {endpoint["id"] for endpoint in endpoints}
    for endpoint in DEFAULT_SETTINGS["llm_settings"]["endpoints"]:
        if endpoint["id"] not in endpoint_ids:
            endpoints.append(deepcopy(endpoint))
    for endpoint in endpoints:
        if endpoint.get("api_base") == "https://api.deepseek.com/beta":
            endpoint["api_base"] = "https://api.deepseek.com/v1"
        if endpoint.get("api_base") == "https://api.minimax.chat/v1":
            endpoint["api_base"] = "https://api.minimax.cn/v1"

    raw["VERSION"] = "2"
    normalized = VvLlmSettings(**raw).model_dump(mode="json")
    # vv-llm also carries historical models; keep them out of application settings.
    for provider, backend in normalized["backends"].items():
        backend["models"] = {name: model for name, model in backend["models"].items() if not is_retired_model(provider, name)}
        default_model = {"mistral": "mistral-small-latest"}.get(provider, CHAT_CATALOG["default_models"].get(provider))
        if default_model not in backend["models"]:
            default_model = next(iter(backend["models"]), "")
        backend["default_model"] = default_model
    data["llm_settings"] = normalized
    for field in ("auto_title_model", "tool_call_data_generate_model"):
        selection = data.get("agent", {}).get(field)
        if selection and len(selection) == 2 and is_retired_model(str(selection[0]).lower(), selection[1]):
            data["agent"][field] = deepcopy(DEFAULT_SETTINGS["agent"][field])


def _split_endpoint_base_and_path(api_base: str, default_path: str = "/embed") -> tuple[str, str]:
    parsed = urlsplit(api_base)
    if not parsed.scheme or not parsed.netloc:
        return api_base, default_path

    raw_path = parsed.path.rstrip("/")
    if not raw_path:
        return urlunsplit((parsed.scheme, parsed.netloc, "", "", "")), default_path

    base_path, _, endpoint_path = raw_path.rpartition("/")
    if not endpoint_path:
        return urlunsplit((parsed.scheme, parsed.netloc, "", "", "")), raw_path

    endpoint_base = urlunsplit((parsed.scheme, parsed.netloc, base_path, "", ""))
    endpoint_path_value = f"/{endpoint_path}"
    return endpoint_base, endpoint_path_value


def normalize_embedding_backends(data: dict[str, Any]) -> bool:
    llm_settings = data.get("llm_settings")
    if not isinstance(llm_settings, dict):
        return False

    changed = False
    raw_embedding_backends = llm_settings.get("embedding_backends")
    existing_embedding_backends: dict[str, Any] = dict(raw_embedding_backends) if isinstance(raw_embedding_backends, Mapping) else {}
    normalized_embedding_backends = deep_merge(deepcopy(DEFAULT_EMBEDDING_BACKENDS), existing_embedding_backends)

    legacy_embedding_models = data.pop("embedding_models", None)
    if isinstance(legacy_embedding_models, Mapping):
        tei_settings = legacy_embedding_models.get("text_embeddings_inference")
        if isinstance(tei_settings, Mapping):
            endpoint_base, endpoint_path = _split_endpoint_base_and_path(str(tei_settings.get("api_base", "http://localhost:8080/embed")))
            endpoint_list = llm_settings.setdefault("endpoints", [])
            tei_endpoint = next(
                (endpoint for endpoint in endpoint_list if isinstance(endpoint, dict) and endpoint.get("id") == "tei-default"),
                None,
            )
            if tei_endpoint is None:
                tei_endpoint = {
                    "id": "tei-default",
                    "api_base": endpoint_base,
                    "api_key": "",
                }
                endpoint_list.append(tei_endpoint)
            tei_endpoint["api_base"] = endpoint_base
            tei_endpoint["api_key"] = str(tei_settings.get("api_key", ""))

            tei_model_settings = normalized_embedding_backends["custom"]["models"]["text-embeddings-inference"]
            tei_model_settings["endpoints"] = ["tei-default"]
            tei_model_settings["request_mapping"] = {
                "method": "POST",
                "path": endpoint_path or "/embed",
                "body_template": {
                    "inputs": "${inputs}",
                },
            }
            changed = True

    if raw_embedding_backends != normalized_embedding_backends:
        llm_settings["embedding_backends"] = normalized_embedding_backends
        changed = True

    return changed


def update_llm_settings_to_v2(data: dict):
    if data.get("settings_version", 1) == 2:
        normalize_chat_backends(data)
        return data

    llm_settings = deepcopy(DEFAULT_SETTINGS["llm_settings"])

    # 转换 OpenAI 相关设置
    if data.get("openai_api_type") == "open_ai":
        llm_settings["endpoints"].append(
            {
                "id": "openai-default",
                "api_base": data.get("openai_api_base", "https://api.openai.com/v1"),
                "api_key": data.get("openai_api_key", ""),
                "rpm": 900,
                "tpm": 150000,
            }
        )
        llm_settings["backends"]["openai"]["default_endpoint"] = "openai-default"
    else:
        azure_endpoints = data.get("azure_openai", {}).get("endpoints", [])
        for endpoint in azure_endpoints:
            endpoint["id"] = endpoint["api_base"]
            endpoint["is_azure"] = True
            llm_settings["endpoints"].append(endpoint)
        for model_id, model_deployment in [
            ("gpt-35-turbo", "gpt_35_deployment"),
            ("gpt-4", "gpt_4_deployment"),
            ("gpt-4o", "gpt_4o_deployment"),
            ("gpt-4o-mini", "gpt_4o_mini_deployment"),
            ("whisper-1", "whisper_deployment"),
            ("tts-1", "tts_deployment"),
            ("tts-1-hd", "tts_hd_deployment"),
            ("dall-e-3", "dalle3_deployment"),
            ("text-embedding-ada-002", "text_embedding_ada_002_deployment"),
        ]:
            endpoint_id = data.get("azure_openai", {}).get(model_deployment, {}).get("endpoint_id", 0)
            if not azure_endpoints:
                continue
            llm_settings["backends"]["openai"]["models"][model_id] = {
                "id": model_id,
                "endpoints": [azure_endpoints[endpoint_id]["id"]],
            }
    # 转换其他 API 设置
    api_settings = [
        ("moonshot", "moonshot_api_base", "moonshot_api_key"),
        ("zhipuai", "zhipuai_api_base", "zhipuai_api_key"),
        ("anthropic", "anthropic_api_base", "anthropic_api_key"),
        ("minimax", "minimax_api_base", "minimax_api_key"),
        ("qwen", "qwen_api_base", "qwen_api_key"),
        ("mistral", "mistral_api_base", "mistral_api_key"),
        ("deepseek", "deepseek_api_base", "deepseek_api_key"),
        ("yi", "lingyiwanwu_api_base", "lingyiwanwu_api_key"),
        ("gemini", "gemini_api_base", "gemini_api_key"),
        ("groq", "groq_api_base", "groq_api_key"),
        ("baichuan", "baichuan_api_base", "baichuan_api_key"),
    ]

    for provider, api_base_key, api_key_key in api_settings:
        if data.get(api_key_key):
            llm_settings["endpoints"].append(
                {
                    "id": f"{provider}-default",
                    "api_base": data.get(api_base_key, ""),
                    "api_key": data.get(api_key_key, ""),
                }
            )
            for model in llm_settings["backends"][provider]["models"].values():
                model["endpoints"] = [f"{provider}-default"]

    local_llms = data.get("local_llms", [])
    local_endpoints = {}
    for llm in local_llms:
        api_base = llm["api_base"]
        api_key = llm["api_key"]
        if (api_base, api_key) not in local_endpoints:
            local_endpoints[(api_base, api_key)] = {
                "id": f"local-{api_base.lower()}",
                "api_base": api_base,
                "api_key": api_key,
                "rpm": llm["models"][0].get("rpm", 60),
                "tpm": 1000000,
                "concurrent_requests": llm["models"][0].get("concurrent", 1),
            }
            llm_settings["endpoints"].append(local_endpoints[(api_base, api_key)])
        llm["endpoints"] = [local_endpoints[(api_base, api_key)]["id"]]

    custom_llm_families = {}
    for llm in local_llms:
        custom_llm_families[llm["model_family"]] = []
        for model in llm["models"]:
            model_id = model["model_id"]
            llm_settings["backends"]["local"]["models"][model_id] = {
                "id": model_id,
                "endpoints": llm["endpoints"],
                "function_call_available": model.get("function_calling", False),
                "response_format_available": False,
                "context_length": model.get("max_tokens", 32768),
                "max_output_tokens": model.get("max_tokens", None),
            }
            custom_llm_families[llm["model_family"]].append(model_id)
    data["custom_llms"] = custom_llm_families

    v1_fields = [
        "openai_api_type",
        "openai_api_key",
        "openai_api_base",
        "azure_openai",
        "baichuan_api_base",
        "baichuan_api_key",
        "moonshot_api_base",
        "moonshot_api_key",
        "zhipuai_api_base",
        "zhipuai_api_key",
        "anthropic_api_base",
        "anthropic_api_key",
        "minimax_api_base",
        "minimax_api_key",
        "qwen_api_base",
        "qwen_api_key",
        "mistral_api_base",
        "mistral_api_key",
        "deepseek_api_base",
        "deepseek_api_key",
        "lingyiwanwu_api_base",
        "lingyiwanwu_api_key",
        "gemini_api_base",
        "gemini_api_key",
        "groq_api_base",
        "groq_api_key",
        "local_llms",
    ]
    for field in v1_fields:
        if field in data:
            del data[field]

    data["settings_version"] = 2
    data["llm_settings"] = llm_settings
    normalize_chat_backends(data)
    return data


normalize_chat_backends(DEFAULT_SETTINGS)


class Settings:
    def __init__(self):
        self.data = dict()
        try:
            self.load_setting()
        except Exception:
            self.data = dict()

    def load_setting(self):
        from models import model_serializer
        from models import Setting as SettingModel

        if SettingModel.select().count() == 0:
            setting = SettingModel.create(data=deepcopy(DEFAULT_SETTINGS))
        else:
            setting = SettingModel.select().order_by(SettingModel.create_time.desc()).first()
            previous_data = deepcopy(setting.data)
            setting.data = update_llm_settings_to_v2(setting.data)
            setting.data = deep_merge(deepcopy(DEFAULT_SETTINGS), setting.data)
            normalize_embedding_backends(setting.data)
            if setting.data != previous_data:
                setting.save()

        self.data = model_serializer(setting)["data"]

    def __getattribute__(self, name: str) -> Any:
        if name == "data":
            return super().__getattribute__(name)
        if name in super().__getattribute__("data"):
            return super().__getattribute__("data")[name]
        return super().__getattribute__(name)

    def get(self, name: str, default: Any = None) -> Any:
        """
        Retrieve a value from the settings data using a dot-separated key.

        This method allows you to access nested dictionary values using a
        dot-separated string to specify the key hierarchy. If any part of
        the specified key is not found, the method returns the provided
        default value.

        Parameters:
        name (str): A dot-separated string representing the key hierarchy
                    to access the desired value.
        default: The value to return if the specified key is not found.
                 Defaults to None.

        Returns:
        The value corresponding to the specified key hierarchy if found,
        otherwise the default value.

        Example:
        ```python
        settings = Settings()
        value = settings.get("level1.level2", "default")
        # If data is {"level1": {"level2": "abc"}}, value will be "abc"
        # If "level1.level2" does not exist, value will be "default"
        ```
        """
        keys = name.split(".")
        value = self.data
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
