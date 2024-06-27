# @Author: Bi Ying
# @Date:   2024-03-29 01:30:41
from .base_llm import BaseLLMTask
from .types.model import ModelSetting, EndpointSetting


endpoints = [
    EndpointSetting(
        endpoint_settings_key="qwen_api_base",
        api_key_settings_key="qwen_api_key",
        rpm=50,
        tpm=1000000,
    )
]


class QwenTask(BaseLLMTask):
    NAME: str = "qwen"
    DEFAULT_MODEL: str = "qwen1.5-72b-chat"
    MODEL_SETTINGS: dict[str, ModelSetting] = {
        "qwen1.5-7b-chat": ModelSetting(
            id="qwen1.5-7b-chat",
            endpoints=endpoints,
            max_tokens=8000,
            max_output_tokens=2000,
            concurrent=20,
        ),
        "qwen1.5-14b-chat": ModelSetting(
            id="qwen1.5-14b-chat",
            endpoints=endpoints,
            max_tokens=8000,
            max_output_tokens=2000,
            concurrent=20,
        ),
        "qwen1.5-32b-chat": ModelSetting(
            id="qwen1.5-32b-chat",
            endpoints=endpoints,
            max_tokens=30000,
            max_output_tokens=2000,
            concurrent=20,
        ),
        "qwen1.5-72b-chat": ModelSetting(
            id="qwen1.5-72b-chat",
            endpoints=endpoints,
            max_tokens=30000,
            max_output_tokens=2000,
            concurrent=20,
        ),
        "qwen1.5-110b-chat": ModelSetting(
            id="qwen1.5-110b-chat",
            endpoints=endpoints,
            max_tokens=30000,
            max_output_tokens=8000,
            concurrent=20,
        ),
        "qwen2-72b-instruct": ModelSetting(
            id="qwen2-72b-instruct",
            endpoints=endpoints,
            max_tokens=128000,
            max_output_tokens=6144,
            concurrent=20,
        ),
    }
