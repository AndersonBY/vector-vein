"""Application chat catalog sourced from vv-llm's shared contract."""

from copy import deepcopy

from vv_llm.contract import load_catalog


CHAT_CATALOG = load_catalog()

# Older generations are retired from the application's built-in selection.
RETIRED_MODEL_PREFIXES = {
    "openai": ("gpt-3", "gpt-4", "o1", "o3", "o4"),
    "anthropic": ("claude-3",),
    "qwen": ("qwen2", "qwq-"),
    "deepseek": ("deepseek-chat", "deepseek-reasoner"),
    "groq": ("mixtral-", "llama3-", "gemma", "llama-3.1-70b"),
    "mistral": ("open-mistral-7b", "open-mixtral-"),
    "ernie": ("ernie-3.5", "ernie-4.0"),
}

# Built-in entries removed from the shared catalog; custom names remain intact.
RETIRED_LEGACY_MODELS = {
    "openai": [
        "o1",
        "o3-mini-high",
        "text-embedding-ada-002",
    ],
    "anthropic": [
        "claude-3-haiku-20240307",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
    ],
    "minimax": [
        "MiniMax-Text-01",
        "abab5-chat",
        "abab5.5-chat",
        "abab6-chat",
        "abab6.5s-chat",
    ],
    "gemini": [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite-preview-02-05",
        "gemini-2.0-flash-thinking-exp-01-21",
        "gemini-2.0-flash-thinking-exp-1219",
        "gemini-2.0-pro-exp-02-05",
    ],
    "mistral": [
        "codestral",
        "codestral-mamba",
        "mistral-embed",
        "mistral-large",
        "mistral-nemo",
        "mistral-small",
        "pixtral",
    ],
    "qwen": ["qwq-32b-preview"],
    "baichuan": ["Baichuan3-Turbo"],
    "zhipuai": [
        "glm-3-turbo",
        "glm-4",
        "glm-4-0520",
        "glm-4-air",
        "glm-4-airx",
        "glm-4-flash",
        "glm-4-flashx",
        "glm-4-long",
        "glm-4-plus",
        "glm-4v",
        "glm-4v-flash",
        "glm-4v-plus",
        "glm-zero-preview",
    ],
    "moonshot": [
        "moonshot-v1-128k",
        "moonshot-v1-128k-vision-preview",
        "moonshot-v1-32k",
        "moonshot-v1-32k-vision-preview",
        "moonshot-v1-8k",
        "moonshot-v1-8k-vision-preview",
    ],
    "stepfun": ["step-1v-8k", "step-2-16k"],
    "xai": ["grok-2-1212", "grok-2-vision-1212"],
    "ernie": ["ernie-3.5", "ernie-4.0", "ernie-4.5"],
}


def is_retired_model(provider: str, model: str) -> bool:
    return model in RETIRED_LEGACY_MODELS.get(provider, ()) or (
        model in CHAT_CATALOG["backends"].get(provider, {}).get("models", {}) and model.startswith(RETIRED_MODEL_PREFIXES.get(provider, ()))
    )


DEFAULT_CHAT_BACKENDS = {
    provider: {
        "default_endpoint": "lingyiwanwu-default" if provider == "yi" else f"{provider}-default",
        "models": {name: deepcopy(model) for name, model in backend["models"].items() if not is_retired_model(provider, name)},
    }
    for provider, backend in CHAT_CATALOG["backends"].items()
}
DEFAULT_CHAT_BACKENDS["local"] = {"models": {}}

# Existing audio/image nodes obtain their SDK routing through the OpenAI backend.
# Keep these service bindings available without exposing them as chat choices.
OPENAI_SERVICE_MODELS = ("whisper-1", "tts-1", "tts-1-hd", "dall-e-3")
DEFAULT_CHAT_BACKENDS["openai"]["models"].update({name: {"id": name, "enabled": False} for name in OPENAI_SERVICE_MODELS})
