# @Author: Bi Ying
# @Date:   2024-03-29 01:37:01
from .base_llm import BaseLLMTask
from .types.model import ModelSetting, EndpointSetting


class LineYiWanWuTask(BaseLLMTask):
    NAME: str = "ling_yi_wan_wu"
    DEFAULT_MODEL: str = "yi-34b-chat"
    MODEL_SETTINGS: dict[str, ModelSetting] = {
        "yi-large": ModelSetting(
            id="yi-large",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="lingyiwanwu_api_base",
                    api_key_settings_key="lingyiwanwu_api_key",
                    rpm=10,
                    tpm=80000,
                )
            ],
            max_tokens=13000,
            concurrent=5,
        ),
        "yi-large-turbo": ModelSetting(
            id="yi-large-turbo",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="lingyiwanwu_api_base",
                    api_key_settings_key="lingyiwanwu_api_key",
                    rpm=20,
                    tpm=120000,
                )
            ],
            max_tokens=13000,
            concurrent=5,
        ),
        "yi-medium": ModelSetting(
            id="yi-medium",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="lingyiwanwu_api_base",
                    api_key_settings_key="lingyiwanwu_api_key",
                    rpm=20,
                    tpm=120000,
                )
            ],
            max_tokens=13000,
            concurrent=5,
        ),
        "yi-medium-200k": ModelSetting(
            id="yi-medium-200k",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="lingyiwanwu_api_base",
                    api_key_settings_key="lingyiwanwu_api_key",
                    rpm=10,
                    tpm=300000,
                )
            ],
            max_tokens=180000,
            concurrent=3,
        ),
        "yi-spark": ModelSetting(
            id="yi-spark",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="lingyiwanwu_api_base",
                    api_key_settings_key="lingyiwanwu_api_key",
                    rpm=20,
                    tpm=120000,
                )
            ],
            max_tokens=13000,
            concurrent=5,
        ),
        "yi-34b-chat": ModelSetting(
            id="yi-34b-chat-0205",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="lingyiwanwu_api_base",
                    api_key_settings_key="lingyiwanwu_api_key",
                    rpm=20,
                    tpm=64000,
                )
            ],
            max_tokens=3400,
            concurrent=3,
        ),
        "yi-34b-chat-200k": ModelSetting(
            id="yi-34b-chat-200k",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="lingyiwanwu_api_base",
                    api_key_settings_key="lingyiwanwu_api_key",
                    rpm=4,
                    tpm=200000,
                )
            ],
            max_tokens=200000,
            concurrent=1,
        ),
    }
