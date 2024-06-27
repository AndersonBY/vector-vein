# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-12-12 15:24:15
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-17 13:32:40
from .openai_compatible_client import OpenAICompatibleChatClient, AsyncOpenAICompatibleChatClient


DEFAULT_MODEL = "qwen2-72b-instruct"
MODEL_MAX_INPUT_LENGTH = {
    "qwen1.5-1.8b-chat": 30000,
    "qwen1.5-4b-chat": 30000,
    "qwen1.5-7b-chat": 30000,
    "qwen1.5-14b-chat": 30000,
    "qwen1.5-32b-chat": 30000,
    "qwen1.5-72b-chat": 30000,
    "qwen1.5-110b-chat": 30000,
    "qwen2-72b-instruct": 128000,
}
MODEL_FUNCTION_CALLING_AVAILABLE = {
    "qwen1.5-1.8b-chat": False,
    "qwen1.5-4b-chat": False,
    "qwen1.5-7b-chat": False,
    "qwen1.5-14b-chat": False,
    "qwen1.5-32b-chat": False,
    "qwen1.5-72b-chat": False,
    "qwen1.5-110b-chat": False,
    "qwen2-72b-instruct": False,
}

API_KEY_SETTING_NAME = "qwen_api_key"
API_BASE_SETTING_NAME = "qwen_api_base"


class QwenChatClient(OpenAICompatibleChatClient):
    DEFAULT_MODEL = DEFAULT_MODEL
    MODEL_MAX_INPUT_LENGTH = MODEL_MAX_INPUT_LENGTH
    MODEL_FUNCTION_CALLING_AVAILABLE = MODEL_FUNCTION_CALLING_AVAILABLE
    API_KEY_SETTING_NAME = API_KEY_SETTING_NAME
    API_BASE_SETTING_NAME = API_BASE_SETTING_NAME


class AsyncQwenChatClient(AsyncOpenAICompatibleChatClient):
    DEFAULT_MODEL = DEFAULT_MODEL
    MODEL_MAX_INPUT_LENGTH = MODEL_MAX_INPUT_LENGTH
    MODEL_FUNCTION_CALLING_AVAILABLE = MODEL_FUNCTION_CALLING_AVAILABLE
    API_KEY_SETTING_NAME = API_KEY_SETTING_NAME
    API_BASE_SETTING_NAME = API_BASE_SETTING_NAME
