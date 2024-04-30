# @Author: Bi Ying
# @Date:   2024-03-29 01:35:54
from .base_llm import BaseLLMTask
from .types.model import ModelSetting, EndpointSetting


endpoints = [
    EndpointSetting(
        endpoint_settings_key="moonshot_api_base",
        api_key_settings_key="moonshot_api_key",
        rpm=20,
        tpm=200000,
    )
]


class MoonshotTask(BaseLLMTask):
    NAME: str = "moonshot"
    DEFAULT_MODEL: str = "moonshot-v1-8k"
    MODEL_SETTINGS: dict[str, ModelSetting] = {
        "moonshot-v1-8k": ModelSetting(
            id="moonshot-v1-8k",
            endpoints=endpoints,
            max_tokens=8192,
        ),
        "moonshot-v1-32k": ModelSetting(
            id="moonshot-v1-32k",
            endpoints=endpoints,
            max_tokens=32768,
        ),
        "moonshot-v1-128k": ModelSetting(
            id="moonshot-v1-128k",
            endpoints=endpoints,
            max_tokens=131072,
        ),
    }
