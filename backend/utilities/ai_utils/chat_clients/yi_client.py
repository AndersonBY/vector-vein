# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-12-12 15:24:15
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-17 17:40:53
from .openai_compatible_client import OpenAICompatibleChatClient, AsyncOpenAICompatibleChatClient


DEFAULT_MODEL = "yi-large-turbo"
MODEL_MAX_INPUT_LENGTH = {
    "yi-large": 32000,
    "yi-large-turbo": 16000,
    "yi-medium": 16000,
    "yi-medium-200k": 200000,
    "yi-spark": 16000,
    "yi-vision": 4000,
}
MODEL_FUNCTION_CALLING_AVAILABLE = {
    "yi-large": False,
    "yi-large-turbo": False,
    "yi-medium": False,
    "yi-medium-200k": False,
    "yi-spark": False,
    "yi-vision": False,
}

API_KEY_SETTING_NAME = "lingyiwanwu_api_key"
API_BASE_SETTING_NAME = "lingyiwanwu_api_base"


class YiChatClient(OpenAICompatibleChatClient):
    DEFAULT_MODEL = DEFAULT_MODEL
    MODEL_MAX_INPUT_LENGTH = MODEL_MAX_INPUT_LENGTH
    MODEL_FUNCTION_CALLING_AVAILABLE = MODEL_FUNCTION_CALLING_AVAILABLE
    API_KEY_SETTING_NAME = API_KEY_SETTING_NAME
    API_BASE_SETTING_NAME = API_BASE_SETTING_NAME


class AsyncYiChatClient(AsyncOpenAICompatibleChatClient):
    DEFAULT_MODEL = DEFAULT_MODEL
    MODEL_MAX_INPUT_LENGTH = MODEL_MAX_INPUT_LENGTH
    MODEL_FUNCTION_CALLING_AVAILABLE = MODEL_FUNCTION_CALLING_AVAILABLE
    API_KEY_SETTING_NAME = API_KEY_SETTING_NAME
    API_BASE_SETTING_NAME = API_BASE_SETTING_NAME
