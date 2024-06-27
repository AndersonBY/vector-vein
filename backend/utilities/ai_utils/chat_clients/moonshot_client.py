# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-12-12 15:24:15
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-17 13:29:57
from .openai_compatible_client import OpenAICompatibleChatClient, AsyncOpenAICompatibleChatClient


DEFAULT_MODEL = "moonshot-v1-8k"
MODEL_MAX_INPUT_LENGTH = {
    "moonshot-v1-8k": 8000,
    "moonshot-v1-32k": 32000,
    "moonshot-v1-128k": 128000,
}
MODEL_FUNCTION_CALLING_AVAILABLE = {
    "moonshot-v1-8k": True,
    "moonshot-v1-32k": True,
    "moonshot-v1-128k": True,
}

API_KEY_SETTING_NAME = "moonshot_api_key"
API_BASE_SETTING_NAME = "moonshot_api_base"


class MoonshotChatClient(OpenAICompatibleChatClient):
    DEFAULT_MODEL = DEFAULT_MODEL
    MODEL_MAX_INPUT_LENGTH = MODEL_MAX_INPUT_LENGTH
    MODEL_FUNCTION_CALLING_AVAILABLE = MODEL_FUNCTION_CALLING_AVAILABLE
    API_KEY_SETTING_NAME = API_KEY_SETTING_NAME
    API_BASE_SETTING_NAME = API_BASE_SETTING_NAME


class AsyncMoonshotChatClient(AsyncOpenAICompatibleChatClient):
    DEFAULT_MODEL = DEFAULT_MODEL
    MODEL_MAX_INPUT_LENGTH = MODEL_MAX_INPUT_LENGTH
    MODEL_FUNCTION_CALLING_AVAILABLE = MODEL_FUNCTION_CALLING_AVAILABLE
    API_KEY_SETTING_NAME = API_KEY_SETTING_NAME
    API_BASE_SETTING_NAME = API_BASE_SETTING_NAME
