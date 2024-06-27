# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-12-12 15:22:44
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-18 02:18:07
from typing import Literal

from .yi_client import YiChatClient, AsyncYiChatClient
from .base_client import BaseChatClient, BaseAsyncChatClient
from .groq_client import GroqChatClient, AsyncGroqChatClient
from .qwen_client import QwenChatClient, AsyncQwenChatClient
from .local_client import LocalChatClient, AsyncLocalChatClient
from .gemini_client import GeminiChatClient, AsyncGeminiChatClient
from .openai_client import OpenAIChatClient, AsyncOpenAIChatClient
from .zhipuai_client import ZhiPuAIChatClient, AsyncZhiPuAIChatClient
from .minimax_client import MiniMaxChatClient, AsyncMiniMaxChatClient
from .mistral_client import MistralChatClient, AsyncMistralChatClient
from .moonshot_client import MoonshotChatClient, AsyncMoonshotChatClient
from .deepseek_client import DeepSeekChatClient, AsyncDeepSeekChatClient
from .anthropic_client import AnthropicChatClient, AsyncAnthropicChatClient


BackendType = Literal[
    "openai",
    "zhipuai",
    "minimax",
    "moonshot",
    "anthropic",
    "mistral",
    "deepseek",
    "qwen",
    "groq",
    "local",
    "yi",
    "gemini",
]
BackendMap = {
    "sync": {
        "openai": OpenAIChatClient,
        "zhipuai": ZhiPuAIChatClient,
        "minimax": MiniMaxChatClient,
        "moonshot": MoonshotChatClient,
        "anthropic": AnthropicChatClient,
        "mistral": MistralChatClient,
        "deepseek": DeepSeekChatClient,
        "qwen": QwenChatClient,
        "groq": GroqChatClient,
        "local": LocalChatClient,
        "yi": YiChatClient,
        "gemini": GeminiChatClient,
    },
    "async": {
        "openai": AsyncOpenAIChatClient,
        "zhipuai": AsyncZhiPuAIChatClient,
        "minimax": AsyncMiniMaxChatClient,
        "moonshot": AsyncMoonshotChatClient,
        "anthropic": AsyncAnthropicChatClient,
        "mistral": AsyncMistralChatClient,
        "deepseek": AsyncDeepSeekChatClient,
        "qwen": AsyncQwenChatClient,
        "groq": AsyncGroqChatClient,
        "local": AsyncLocalChatClient,
        "yi": AsyncYiChatClient,
        "gemini": AsyncGeminiChatClient,
    },
}


def create_chat_client(
    backend: BackendType,
    model: str | None = None,
    stream: bool = True,
    temperature: float = 0.7,
    context_length_control: str = "latest",
    **kwargs,
) -> BaseChatClient:
    if backend.startswith("_local__"):
        backend = "local"
        family_param = {"family": backend.removeprefix("_local__")}
    elif backend.lower() not in BackendMap["sync"]:
        raise ValueError(f"Unsupported backend: {backend}")
    else:
        backend_key = backend.lower()
        family_param = {}

    ClientClass = BackendMap["sync"][backend_key]
    if model is None:
        model = ClientClass.DEFAULT_MODEL
    return BackendMap["sync"][backend_key](
        model=model,
        stream=stream,
        temperature=temperature,
        context_length_control=context_length_control,
        **family_param,
        **kwargs,
    )


def create_async_chat_client(
    backend: BackendType,
    model: str | None = None,
    stream: bool = True,
    temperature: float = 0.7,
    context_length_control: str = "latest",
    **kwargs,
) -> BaseAsyncChatClient:
    if backend.startswith("_local__"):
        backend_key = "local"
        family_param = {"family": backend.removeprefix("_local__")}
    elif backend.lower() not in BackendMap["async"]:
        raise ValueError(f"Unsupported backend: {backend}")
    else:
        backend_key = backend.lower()
        family_param = {}

    ClientClass = BackendMap["async"][backend_key]
    if model is None:
        model = ClientClass.DEFAULT_MODEL
    return BackendMap["async"][backend_key](
        model=model,
        stream=stream,
        temperature=temperature,
        context_length_control=context_length_control,
        **family_param,
        **kwargs,
    )
