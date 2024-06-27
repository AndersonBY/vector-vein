# @Author: Bi Ying
# @Date:   2024-03-29 01:38:17
from .base_llm import BaseLLMTask
from .types.model import ModelSetting, EndpointSetting


class GroqTask(BaseLLMTask):
    NAME: str = "groq"
    DEFAULT_MODEL: str = "mixtral-8x7b-32768"
    MODEL_SETTINGS: dict[str, ModelSetting] = {
        "mixtral-8x7b-32768": ModelSetting(
            id="mixtral-8x7b-32768",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="groq_api_base",
                    api_key_settings_key="groq_api_key",
                    rpm=30,
                    tpm=5000,
                )
            ],
            max_tokens=32768,
            max_output_tokens=4096,
            concurrent=30,
        ),
        "llama3-70b-8192": ModelSetting(
            id="llama3-70b-8192",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="groq_api_base",
                    api_key_settings_key="groq_api_key",
                    rpm=30,
                    tpm=6000,
                )
            ],
            max_tokens=8192,
            max_output_tokens=4096,
            concurrent=30,
        ),
        "llama3-8b-8192": ModelSetting(
            id="llama3-8b-8192",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="groq_api_base",
                    api_key_settings_key="groq_api_key",
                    rpm=30,
                    tpm=30000,
                )
            ],
            max_tokens=8192,
            max_output_tokens=4096,
            concurrent=30,
        ),
        "gemma-7b-it": ModelSetting(
            id="gemma-7b-it",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="groq_api_base",
                    api_key_settings_key="groq_api_key",
                    rpm=30,
                    tpm=15000,
                )
            ],
            max_tokens=8192,
            max_output_tokens=4096,
            concurrent=30,
        ),
    }
