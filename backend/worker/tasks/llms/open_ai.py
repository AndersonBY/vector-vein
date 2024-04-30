# @Author: Bi Ying
# @Date:   2024-03-29 01:07:26
from .base_llm import BaseLLMTask
from .types.model import ModelSetting, EndpointSetting


class OpenAITask(BaseLLMTask):
    NAME: str = "openai"
    DEFAULT_MODEL: str = "gpt-3.5"
    MODEL_SETTINGS: dict[str, ModelSetting] = {
        "gpt-3.5": ModelSetting(
            id="gpt-3.5-turbo",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="openai_api_base",
                    api_key_settings_key="openai_api_key",
                    rpm=3500,
                    tpm=60000,
                    is_azure=False,
                )
            ],
            function_call_available=True,
            response_format_available=True,
            max_tokens=16384,
            max_output_tokens=4096,
            concurrent=15,
        ),
        "gpt-4": ModelSetting(
            id="gpt-4-turbo",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="openai_api_base",
                    api_key_settings_key="openai_api_key",
                    rpm=500,
                    tpm=300000,
                    is_azure=False,
                )
            ],
            function_call_available=True,
            response_format_available=True,
            max_tokens=128000,
            max_output_tokens=4096,
        ),
    }


class AzureOpenAITask(BaseLLMTask):
    NAME: str = "openai"
    DEFAULT_MODEL: str = "gpt-3.5"
    MODEL_SETTINGS: dict[str, ModelSetting] = {
        "gpt-3.5": ModelSetting(
            id_settings_key="azure_gpt_35_deployment_id",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="azure_endpoint",
                    api_key_settings_key="azure_api_key",
                    rpm=3500,
                    tpm=60000,
                    is_azure=True,
                )
            ],
            function_call_available=True,
            response_format_available=True,
            max_tokens=16384,
            max_output_tokens=4096,
            concurrent=15,
        ),
        "gpt-4": ModelSetting(
            id_settings_key="azure_gpt_4_deployment_id",
            endpoints=[
                EndpointSetting(
                    endpoint_settings_key="azure_endpoint",
                    api_key_settings_key="azure_api_key",
                    rpm=500,
                    tpm=300000,
                    is_azure=True,
                )
            ],
            function_call_available=True,
            response_format_available=True,
            max_tokens=128000,
            max_output_tokens=4096,
        ),
    }
