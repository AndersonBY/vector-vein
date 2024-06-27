# @Author: Bi Ying
# @Date:   2024-03-29 01:38:17
from .base_llm import BaseLLMTask
from .types.model import ModelSetting, EndpointSetting


class DeepSeekTask(BaseLLMTask):
    NAME: str = "deepseek"
    DEFAULT_MODEL: str = "deepseek-chat"
    MODEL_SETTINGS: dict[str, ModelSetting] = {
        "deepseek-chat": ModelSetting(
            id="deepseek-chat",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="deepseek_api_base",
                    api_key_settings_key="deepseek_api_key",
                    rpm=200,
                    tpm=320000,
                )
            ],
            max_tokens=30000,
            max_output_tokens=4096,
            concurrent=30,
        ),
        "deepseek-coder": ModelSetting(
            id="deepseek-coder",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="deepseek_api_base",
                    api_key_settings_key="deepseek_api_key",
                    rpm=200,
                    tpm=400000,
                )
            ],
            max_tokens=15000,
            max_output_tokens=4096,
            concurrent=30,
        ),
    }
