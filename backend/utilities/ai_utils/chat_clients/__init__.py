# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-12-12 15:22:44
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-04-30 15:19:21
from typing import Literal

from .base_client import BaseChatClient, BaseAsyncChatClient
from .openai_client import OpenAIChatClient, AsyncOpenAIChatClient
from .zhipuai_client import ZhiPuAIChatClient, AsyncZhiPuAIChatClient
from .minimax_client import MiniMaxChatClient, AsyncMiniMaxChatClient
from .moonshot_client import MoonshotChatClient, AsyncMoonshotChatClient
from .anthropic_client import AnthropicChatClient, AsyncAnthropicChatClient
from .mistral_client import MistralChatClient, AsyncMistralChatClient
from .deepseek_client import DeepSeekChatClient, AsyncDeepSeekChatClient


BackendType = Literal[
    "openai",
    "zhipuai",
    "minimax",
    "moonshot",
    "anthropic",
    "mistral",
    "deepseek",
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
    },
    "async": {
        "openai": AsyncOpenAIChatClient,
        "zhipuai": AsyncZhiPuAIChatClient,
        "minimax": AsyncMiniMaxChatClient,
        "moonshot": AsyncMoonshotChatClient,
        "anthropic": AsyncAnthropicChatClient,
        "mistral": AsyncMistralChatClient,
        "deepseek": AsyncDeepSeekChatClient,
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
    if backend not in BackendMap["sync"]:
        raise ValueError(f"Unsupported backend: {backend}")

    ClientClass = BackendMap["sync"][backend]
    if model is None:
        model = ClientClass.DEFAULT_MODEL
    return BackendMap["sync"][backend](
        model=model,
        stream=stream,
        temperature=temperature,
        context_length_control=context_length_control,
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
    if backend not in BackendMap["async"]:
        raise ValueError(f"Unsupported backend: {backend}")

    ClientClass = BackendMap["async"][backend]
    if model is None:
        model = ClientClass.DEFAULT_MODEL
    return BackendMap["async"][backend](
        model=model,
        stream=stream,
        temperature=temperature,
        context_length_control=context_length_control,
        **kwargs,
    )
