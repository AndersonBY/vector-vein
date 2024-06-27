# @Author: Bi Ying
# @Date:   2024-03-29 01:32:25
from .base_llm import BaseLLMTask
from .types.model import ModelSetting, EndpointSetting


endpoints = [
    EndpointSetting(
        endpoint_settings_key="baichuan_api_base",
        api_key_settings_key="baichuan_api_key",
        rpm=120,
        tpm=200000,
    )
]


class BaiChuanTask(BaseLLMTask):
    NAME: str = "baichuan"
    DEFAULT_MODEL: str = "Baichuan3-Turbo"
    MODEL_SETTINGS: dict[str, ModelSetting] = {
        "Baichuan4": ModelSetting(
            id="Baichuan4",
            endpoints=endpoints,
            max_tokens=32768,
            max_output_tokens=2048,
        ),
        "Baichuan3-Turbo": ModelSetting(
            id="Baichuan3-Turbo",
            endpoints=endpoints,
            max_tokens=32768,
            max_output_tokens=2048,
        ),
        "Baichuan3-Turbo-128k": ModelSetting(
            id="Baichuan3-Turbo-128k",
            endpoints=endpoints,
            max_tokens=128000,
            max_output_tokens=2048,
        ),
        "Baichuan2-Turbo": ModelSetting(
            id="Baichuan2-Turbo",
            endpoints=endpoints,
            max_tokens=32768,
            max_output_tokens=2048,
        ),
        "Baichuan2-Turbo-192k": ModelSetting(
            id="Baichuan2-Turbo-192k",
            endpoints=endpoints,
            max_tokens=192000,
            max_output_tokens=2048,
        ),
        "Baichuan2-53B": ModelSetting(
            id="Baichuan2-53B",
            endpoints=endpoints,
            max_tokens=8192,
            max_output_tokens=2048,
        ),
    }
