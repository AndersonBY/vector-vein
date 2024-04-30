# @Author: Bi Ying
# @Date:   2024-03-29 01:35:54
from .base_llm import BaseLLMTask
from .types.model import ModelSetting, EndpointSetting


endpoints = [
    EndpointSetting(
        endpoint_settings_key="zhipuai_api_base",
        api_key_settings_key="zhipuai_api_key",
        rpm=20,
        tpm=200000,
    )
]


class ChatGLMTask(BaseLLMTask):
    NAME: str = "chatglm"
    DEFAULT_MODEL: str = "glm-3-turbo"
    MODEL_SETTINGS: dict[str, ModelSetting] = {
        "glm-3-turbo": ModelSetting(
            id="glm-3-turbo",
            endpoints=endpoints,
            max_output_tokens=8192,
        ),
        "glm-4": ModelSetting(
            id="glm-4",
            endpoints=endpoints,
            max_output_tokens=8192,
        ),
    }
