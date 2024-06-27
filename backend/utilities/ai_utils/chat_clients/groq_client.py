# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-12-12 15:24:15
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-17 13:30:42
from .openai_compatible_client import OpenAICompatibleChatClient, AsyncOpenAICompatibleChatClient


DEFAULT_MODEL = "llama3-70b-8192"
MODEL_MAX_INPUT_LENGTH = {
    "mixtral-8x7b-32768": 32768,
    "llama3-70b-8192": 8192,
    "llama3-8b-8192": 8192,
    "gemma-7b-it": 8192,
}
MODEL_FUNCTION_CALLING_AVAILABLE = {
    "mixtral-8x7b-32768": True,
    "llama3-70b-8192": True,
    "llama3-8b-8192": True,
    "gemma-7b-it": True,
}

API_KEY_SETTING_NAME = "groq_api_key"
API_BASE_SETTING_NAME = "groq_api_base"


class GroqChatClient(OpenAICompatibleChatClient):
    DEFAULT_MODEL = DEFAULT_MODEL
    MODEL_MAX_INPUT_LENGTH = MODEL_MAX_INPUT_LENGTH
    MODEL_FUNCTION_CALLING_AVAILABLE = MODEL_FUNCTION_CALLING_AVAILABLE
    API_KEY_SETTING_NAME = API_KEY_SETTING_NAME
    API_BASE_SETTING_NAME = API_BASE_SETTING_NAME


class AsyncGroqChatClient(AsyncOpenAICompatibleChatClient):
    DEFAULT_MODEL = DEFAULT_MODEL
    MODEL_MAX_INPUT_LENGTH = MODEL_MAX_INPUT_LENGTH
    MODEL_FUNCTION_CALLING_AVAILABLE = MODEL_FUNCTION_CALLING_AVAILABLE
    API_KEY_SETTING_NAME = API_KEY_SETTING_NAME
    API_BASE_SETTING_NAME = API_BASE_SETTING_NAME
