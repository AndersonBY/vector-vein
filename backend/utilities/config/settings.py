# @Author: Bi Ying
# @Date:   2024-04-29 16:50:17
import json
from typing import Any
from collections.abc import Mapping


DEFAULT_SETTINGS = {
    "initial_setup": False,
    "settings_version": 2,
    "output_folder": "./",
    "data_path": "./data",
    "log_path": "./log",
    "email": {"user": "", "password": "", "smtp_host": "", "smtp_port": "", "smtp_ssl": True},
    "pexels_api_key": "",
    "stable_diffusion_base_url": "http://127.0.0.1:7860",
    "stability_key": "",
    "use_system_proxy": True,
    "skip_ssl_verification": False,
    "website_domain": "vectorvein.ai",
    "agent": {
        "auto_title": True,
        "auto_title_model": ["OpenAI", "gpt-4o-mini"],
        "screenshot_monitor_device": 0,
        "tool_call_data_generate_model": ["OpenAI", "gpt-4o-mini"],
    },
    "microphone_device": 0,
    "shortcuts": {},
    "embedding_models": {"text_embeddings_inference": {"api_base": "http://localhost:8080/embed"}},
    "tts": {
        "piper": {"api_base": "http://localhost:5000"},
        "reecho": {"api_key": "", "voices": []},
        "azure": {"api_key": "", "service_region": "", "voices": []},
    },
    "asr": {
        "provider": "openai",
        "openai": {"same_as_llm": True, "api_base": "https://api.openai.com/v1", "api_key": "", "model": "whisper-1"},
        "deepgram": {"api_key": "", "speech_to_text": {"model": "nova-2", "language": "en"}},
    },
    "web_search": {
        "jinaai": {"api_key": ""},
        "bing": {"ocp_apim_subscription_key": "", "endpoint": "https://api.bing.microsoft.com/v7.0/search"},
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
                "endpoint_name": "",
                "api_key": "",
                "rpm": 900,
                "tpm": 150000,
                "is_azure": True,
            },
            {
                "id": "anthropic-default",
                "api_base": "https://api.anthropic.com/v1",
                "api_key": "",
            },
            {
                "id": "vertex-anthropic",
                "region": "europe-west1",
                "api_base": "",
                "credentials": {},
                "is_vertex": True,
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
                "api_base": "https://api.minimax.chat/v1/text/chatcompletion_v2",
                "api_key": "",
            },
            {
                "id": "gemini-default",
                "api_base": "https://generativelanguage.googleapis.com/v1beta",
                "api_key": "",
            },
            {
                "id": "deepseek-default",
                "api_base": "https://api.deepseek.com/beta",
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
        ],
        "openai": {
            "models": {
                "o1": {"id": "o1", "endpoints": ["openai-default"]},
                "o1-mini": {"id": "o1-mini", "endpoints": ["openai-default"]},
                "o1-preview": {"id": "o1-preview", "endpoints": ["openai-default"]},
                "gpt-4o": {"id": "gpt-4o", "endpoints": ["openai-default"]},
                "gpt-4o-mini": {"id": "gpt-4o-mini", "endpoints": ["openai-default"]},
                "gpt-4": {"id": "gpt-4", "endpoints": ["openai-default"]},
                "gpt-35-turbo": {"id": "gpt-3.5-turbo", "endpoints": ["openai-default"]},
                "whisper-1": {"id": "whisper-1", "endpoints": ["openai-default"]},
                "tts-1": {"id": "tts-1", "endpoints": ["openai-default"]},
                "tts-1-hd": {"id": "tts-1-hd", "endpoints": ["openai-default"]},
                "dall-e-3": {"id": "dall-e-3", "endpoints": ["openai-default"]},
                "text-embedding-ada-002": {"id": "text-embedding-ada-002", "endpoints": ["openai-default"]},
            }
        },
        "anthropic": {
            "models": {
                "claude-3-opus-20240229": {
                    "id": "claude-3-opus-20240229",
                    "endpoints": ["anthropic-default"],
                },
                "claude-3-sonnet-20240229": {
                    "id": "claude-3-sonnet-20240229",
                    "endpoints": ["anthropic-default"],
                },
                "claude-3-haiku-20240307": {
                    "id": "claude-3-haiku-20240307",
                    "endpoints": ["anthropic-default"],
                },
                "claude-3-5-sonnet-20240620": {
                    "id": "claude-3-5-sonnet-20240620",
                    "endpoints": ["anthropic-default"],
                },
                "claude-3-5-sonnet-20241022": {
                    "id": "claude-3-5-sonnet-20241022",
                    "endpoints": ["anthropic-default"],
                },
                "claude-3-5-haiku-20241022": {
                    "id": "claude-3-5-haiku-20241022",
                    "endpoints": ["anthropic-default"],
                },
            }
        },
        "minimax": {
            "models": {
                "abab5-chat": {"id": "abab5-chat", "endpoints": ["minimax-default"]},
                "abab5.5-chat": {"id": "abab5.5-chat", "endpoints": ["minimax-default"]},
                "abab6-chat": {"id": "abab6-chat", "endpoints": ["minimax-default"]},
                "abab6.5s-chat": {"id": "abab6.5s-chat", "endpoints": ["minimax-default"]},
                "MiniMax-Text-01": {"endpoints": ["minimax-default"], "id": "MiniMax-Text-01"},
            }
        },
        "gemini": {
            "models": {
                "gemini-1.5-pro": {"id": "gemini-1.5-pro", "endpoints": ["gemini-default"]},
                "gemini-1.5-flash": {"id": "gemini-1.5-flash", "endpoints": ["gemini-default"]},
                "gemini-2.0-flash-exp": {"endpoints": ["gemini-default"], "id": "gemini-2.0-flash-exp"},
                "gemini-2.0-flash-thinking-exp-1219": {
                    "endpoints": ["gemini-default"],
                    "id": "gemini-2.0-flash-thinking-exp-1219",
                },
                "gemini-exp-1206": {"endpoints": ["gemini-default"], "id": "gemini-exp-1206"},
            }
        },
        "deepseek": {
            "models": {
                "deepseek-chat": {"id": "deepseek-chat", "endpoints": ["deepseek-default"]},
                "deepseek-reasoner": {"id": "deepseek-reasoner", "endpoints": ["deepseek-default"]},
            }
        },
        "groq": {
            "models": {
                "mixtral-8x7b-32768": {
                    "id": "mixtral-8x7b-32768",
                    "endpoints": ["groq-default"],
                },
                "llama3-70b-8192": {
                    "id": "llama3-70b-8192",
                    "endpoints": ["groq-default"],
                },
                "llama3-8b-8192": {
                    "id": "llama3-8b-8192",
                    "endpoints": ["groq-default"],
                },
                "gemma-7b-it": {
                    "id": "gemma-7b-it",
                    "endpoints": ["groq-default"],
                },
                "gemma2-9b-it": {
                    "id": "gemma2-9b-it",
                    "endpoints": ["groq-default"],
                },
                "llama3-groq-70b-8192-tool-use-preview": {
                    "id": "llama3-groq-70b-8192-tool-use-preview",
                    "endpoints": ["groq-default"],
                },
                "llama3-groq-8b-8192-tool-use-preview": {
                    "id": "llama3-groq-8b-8192-tool-use-preview",
                    "endpoints": ["groq-default"],
                },
                "llama-3.1-70b-versatile": {
                    "id": "llama-3.1-70b-versatile",
                    "endpoints": ["groq-default"],
                },
                "llama-3.1-8b-instant": {
                    "id": "llama-3.1-8b-instant",
                    "endpoints": ["groq-default"],
                },
            }
        },
        "mistral": {
            "models": {
                "mistral-large": {
                    "id": "mistral-large-latest",
                    "context_length": 128000,
                    "function_call_available": True,
                    "response_format_available": True,
                    "endpoints": ["mistral-default"],
                },
                "mistral-small": {
                    "id": "mistral-small-latest",
                    "context_length": 128000,
                    "function_call_available": True,
                    "response_format_available": True,
                    "endpoints": ["mistral-default"],
                },
                "codestral": {
                    "id": "codestral-latest",
                    "context_length": 32000,
                    "function_call_available": True,
                    "response_format_available": True,
                    "endpoints": ["mistral-default"],
                },
                "mistral-embed": {
                    "id": "mistral-embed",
                    "context_length": 8000,
                    "function_call_available": False,
                    "response_format_available": False,
                    "endpoints": ["mistral-default"],
                },
                "pixtral": {
                    "id": "pixtral-12b-2409",
                    "context_length": 128000,
                    "function_call_available": True,
                    "response_format_available": True,
                    "endpoints": ["mistral-default"],
                },
                "mistral-nemo": {
                    "id": "open-mistral-nemo",
                    "context_length": 128000,
                    "function_call_available": True,
                    "response_format_available": True,
                    "endpoints": ["mistral-default"],
                },
                "codestral-mamba": {
                    "id": "open-codestral-mamba",
                    "context_length": 256000,
                    "function_call_available": True,
                    "response_format_available": True,
                    "endpoints": ["mistral-default"],
                },
            }
        },
        "qwen": {
            "models": {
                "qwen2.5-7b-instruct": {
                    "id": "qwen2.5-7b-instruct",
                    "endpoints": ["qwen-default"],
                    "function_call_available": False,
                    "response_format_available": False,
                    "context_length": 131072,
                    "max_output_tokens": 8192,
                },
                "qwen2.5-14b-instruct": {
                    "id": "qwen2.5-14b-instruct",
                    "endpoints": ["qwen-default"],
                    "function_call_available": False,
                    "response_format_available": False,
                    "context_length": 131072,
                    "max_output_tokens": 8192,
                },
                "qwen2.5-32b-instruct": {
                    "id": "qwen2.5-32b-instruct",
                    "endpoints": ["qwen-default"],
                    "function_call_available": False,
                    "response_format_available": False,
                    "context_length": 131072,
                    "max_output_tokens": 8192,
                },
                "qwen2.5-coder-32b-instruct": {
                    "id": "qwen2.5-coder-32b-instruct",
                    "endpoints": ["qwen-default"],
                    "function_call_available": False,
                    "response_format_available": False,
                    "context_length": 131072,
                    "max_output_tokens": 4096,
                },
                "qwen2.5-72b-instruct": {
                    "id": "qwen2.5-72b-instruct",
                    "endpoints": ["qwen-default"],
                    "function_call_available": False,
                    "response_format_available": False,
                    "context_length": 131072,
                    "max_output_tokens": 8192,
                },
                "qwq-32b-preview": {
                    "id": "qwq-32b-preview",
                    "endpoints": ["qwen-default"],
                    "function_call_available": False,
                    "response_format_available": False,
                    "context_length": 32768,
                    "max_output_tokens": 4096,
                },
                "qwen-max": {
                    "id": "qwen-max",
                    "endpoints": ["qwen-default"],
                    "function_call_available": False,
                    "response_format_available": True,
                    "context_length": 8096,
                    "max_output_tokens": 2048,
                },
                "qwen-max-longcontext": {
                    "id": "qwen-max-longcontext",
                    "endpoints": ["qwen-default"],
                    "function_call_available": False,
                    "response_format_available": True,
                    "context_length": 30000,
                    "max_output_tokens": 2048,
                },
                "qwen-plus": {
                    "id": "qwen-plus",
                    "endpoints": ["qwen-default"],
                    "function_call_available": False,
                    "response_format_available": True,
                    "context_length": 131072,
                    "max_output_tokens": 8096,
                },
                "qwen-turbo": {
                    "id": "qwen-turbo",
                    "endpoints": ["qwen-default"],
                    "function_call_available": False,
                    "response_format_available": True,
                    "context_length": 8096,
                    "max_output_tokens": 1500,
                },
            }
        },
        "yi": {
            "models": {
                "yi-large": {"id": "yi-large", "endpoints": ["lingyiwanwu-default"]},
                "yi-large-turbo": {"id": "yi-large-turbo", "endpoints": ["lingyiwanwu-default"]},
                "yi-large-fc": {"id": "yi-large-fc", "endpoints": ["lingyiwanwu-default"]},
                "yi-medium": {"id": "yi-medium", "endpoints": ["lingyiwanwu-default"]},
                "yi-medium-200k": {"id": "yi-medium-200k", "endpoints": ["lingyiwanwu-default"]},
                "yi-spark": {"id": "yi-spark", "endpoints": ["lingyiwanwu-default"]},
                "yi-vision": {"id": "yi-vision", "endpoints": ["lingyiwanwu-default"]},
                "yi-lightning": {"id": "yi-lightning", "endpoints": ["lingyiwanwu-default"]},
            }
        },
        "zhipuai": {
            "models": {
                "glm-3-turbo": {"id": "glm-3-turbo", "endpoints": ["zhipuai-default"]},
                "glm-4": {"id": "glm-4", "endpoints": ["zhipuai-default"]},
                "glm-4-plus": {"id": "glm-4-plus", "endpoints": ["zhipuai-default"]},
                "glm-4-0520": {"id": "glm-4-0520", "endpoints": ["zhipuai-default"]},
                "glm-4-air": {"id": "glm-4-air", "endpoints": ["zhipuai-default"]},
                "glm-4-airx": {"id": "glm-4-airx", "endpoints": ["zhipuai-default"]},
                "glm-4-flash": {"id": "glm-4-flash", "endpoints": ["zhipuai-default"]},
                "glm-4-flashx": {"id": "glm-4-flashx", "endpoints": ["zhipuai-default"]},
                "glm-4-long": {"id": "glm-4-long", "endpoints": ["zhipuai-default"]},
                "glm-4v": {"id": "glm-4v", "endpoints": ["zhipuai-default"]},
                "glm-4v-flash": {"id": "glm-4v-flash", "endpoints": ["zhipuai-default"]},
                "glm-4v-plus": {"id": "glm-4v-plus", "endpoints": ["zhipuai-default"]},
                "glm-zero-preview": {"id": "glm-zero-preview", "endpoints": ["zhipuai-default"]},
            }
        },
        "moonshot": {
            "models": {
                "moonshot-v1-8k": {"id": "moonshot-v1-8k", "endpoints": ["moonshot-default"]},
                "moonshot-v1-32k": {"id": "moonshot-v1-32k", "endpoints": ["moonshot-default"]},
                "moonshot-v1-128k": {"id": "moonshot-v1-128k", "endpoints": ["moonshot-default"]},
            }
        },
        "local": {
            "models": {},
        },
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


def update_llm_settings_to_v2(data: dict):
    from vectorvein.settings import settings as vectorvein_settings

    if data.get("settings_version", 1) == 2:
        return data

    with open("settings_v1.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    llm_settings = vectorvein_settings.model_dump()

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
        for model in [
            "gpt-35-turbo",
            "gpt-4",
            "gpt-4o",
            "gpt-4o-mini",
            "whisper-1",
            "tts-1",
            "tts-1-hd",
            "dall-e-3",
            "text-embedding-ada-002",
        ]:
            llm_settings["openai"]["models"][model] = {"id": model, "endpoints": ["openai-default"]}
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
            llm_settings["openai"]["models"][model_id] = {
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
            for model in llm_settings[provider]["models"].values():
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
            llm_settings["local"]["models"][model_id] = {
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
    vectorvein_settings.load(llm_settings)
    data["llm_settings"] = vectorvein_settings.model_dump()
    return data


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
        from vectorvein.settings import settings as vectorvein_settings

        if SettingModel.select().count() == 0:
            setting = SettingModel.create(data=DEFAULT_SETTINGS)
            vectorvein_settings.load(DEFAULT_SETTINGS["llm_settings"])
            setting.data["llm_settings"] = vectorvein_settings.model_dump()
            setting.save()
        else:
            setting = SettingModel.select().order_by(SettingModel.create_time.desc()).first()
            setting.data = update_llm_settings_to_v2(setting.data)
            setting.data = deep_merge(DEFAULT_SETTINGS.copy(), setting.data)
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
