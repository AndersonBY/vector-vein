# @Author: Bi Ying
# @Date:   2024-03-29 01:35:54
from .base_llm import BaseLLMTask
from .types.model import ModelSetting, EndpointSetting


endpoints_20_rpm = [
    EndpointSetting(
        endpoint_settings_key="zhipuai_api_base",
        api_key_settings_key="zhipuai_api_key",
        rpm=20,
        tpm=2000000,
    )
]

endpoints_100_rpm = [
    EndpointSetting(
        endpoint_settings_key="zhipuai_api_base",
        api_key_settings_key="zhipuai_api_key",
        rpm=100,
        tpm=2000000,
    )
]


class ChatGLMTask(BaseLLMTask):
    NAME: str = "chatglm"
    DEFAULT_MODEL: str = "glm-3-turbo"
    MODEL_SETTINGS: dict[str, ModelSetting] = {
        "glm-3-turbo": ModelSetting(
            id="glm-3-turbo",
            endpoints=endpoints_100_rpm,
            max_output_tokens=4095,
        ),
        "glm-4": ModelSetting(
            id="glm-4",
            endpoints=endpoints_20_rpm,
            max_output_tokens=4095,
        ),
        "glm-4-0520": ModelSetting(
            id="glm-4-0520",
            endpoints=endpoints_20_rpm,
            max_output_tokens=4095,
        ),
        "glm-4-air": ModelSetting(
            id="glm-4-air",
            endpoints=endpoints_100_rpm,
            max_output_tokens=4095,
        ),
        "glm-4-airx": ModelSetting(
            id="glm-4-airx",
            endpoints=endpoints_20_rpm,
            max_output_tokens=4095,
        ),
        "glm-4-flash": ModelSetting(
            id="glm-4-flash",
            endpoints=endpoints_100_rpm,
            max_output_tokens=4095,
        ),
        "chatglm_turbo": ModelSetting(
            id="glm-3-turbo",
            endpoints=endpoints_20_rpm,
            max_output_tokens=4095,
        ),
    }
