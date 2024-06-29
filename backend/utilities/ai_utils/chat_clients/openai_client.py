# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-12-12 15:23:26
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-29 18:13:29
from typing import Union, AsyncGenerator

import httpx
from openai import OpenAI, AsyncOpenAI
from openai import AzureOpenAI, AsyncAzureOpenAI
from openai._streaming import Stream, AsyncStream
from openai._types import NotGiven, NOT_GIVEN
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from utilities.config import Settings
from utilities.network import proxies
from .base_client import BaseChatClient, BaseAsyncChatClient
from .utils import cutoff_messages


MODEL_MAX_INPUT_LENGTH = {
    "gpt-35-turbo": 16385,
    "gpt-4": 128000,
    "gpt-4o": 128000,
    "gpt-4v": 128000,
}


def get_openai_client_and_model(
    is_async: bool = False,
    model_id: str = "",
    api_base: str | None = None,
    api_key: str | None = None,
):
    """Base on user settings, return the OpenAI client and model id"""

    if api_base is not None and api_key is not None:
        if is_async:
            client = AsyncOpenAI(
                api_key=api_key,
                base_url=api_base,
                http_client=httpx.AsyncClient(
                    proxies=proxies(),
                    transport=httpx.HTTPTransport(local_address="0.0.0.0"),
                ),
            )
        else:
            client = OpenAI(
                api_key=api_key,
                base_url=api_base,
                http_client=httpx.Client(
                    proxies=proxies(),
                    transport=httpx.HTTPTransport(local_address="0.0.0.0"),
                ),
            )
        return client, model_id

    settings = Settings()
    if settings.openai_api_type == "azure":
        if model_id == "gpt-35-turbo":
            setting_key = "gpt_35_deployment"
        elif model_id == "gpt-4":
            setting_key = "gpt_4_deployment"
        elif model_id == "gpt-4o":
            setting_key = "gpt_4o_deployment"
        elif model_id == "gpt-4v":
            setting_key = "gpt_4v_deployment"
        elif model_id == "tts-1":
            setting_key = "tts_deployment"
        elif model_id == "tts-1-hd":
            setting_key = "tts_hd_deployment"
        elif model_id == "whisper-1":
            setting_key = "whisper_deployment"
        elif model_id == "text-embedding-ada-002":
            setting_key = "text_embedding_ada_002_deployment"
        elif model_id == "dall-e-3":
            setting_key = "dalle3_deployment"
        else:
            setting_key = model_id

        model_id = settings.get(f"azure_openai.{setting_key}.id")

        if is_async:
            client = AsyncAzureOpenAI(
                azure_endpoint=settings.get(f"azure_openai.{setting_key}.endpoint.api_base"),
                api_key=settings.get(f"azure_openai.{setting_key}.endpoint.api_key"),
                api_version="2024-05-01-preview",
                http_client=httpx.AsyncClient(
                    proxies=proxies(),
                    transport=httpx.HTTPTransport(local_address="0.0.0.0"),
                ),
            )
        else:
            client = AzureOpenAI(
                azure_endpoint=settings.get(f"azure_openai.{setting_key}.endpoint.api_base"),
                api_key=settings.get(f"azure_openai.{setting_key}.endpoint.api_key"),
                api_version="2024-05-01-preview",
                http_client=httpx.Client(
                    proxies=proxies(),
                    transport=httpx.HTTPTransport(local_address="0.0.0.0"),
                ),
            )
    else:
        if is_async:
            client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.get("openai_api_base", "https://api.openai.com/v1"),
                http_client=httpx.AsyncClient(
                    proxies=proxies(),
                    transport=httpx.HTTPTransport(local_address="0.0.0.0"),
                ),
            )
        else:
            client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.get("openai_api_base", "https://api.openai.com/v1"),
                http_client=httpx.Client(
                    proxies=proxies(),
                    transport=httpx.HTTPTransport(local_address="0.0.0.0"),
                ),
            )

    return client, model_id


class OpenAIChatClient(BaseChatClient):
    DEFAULT_MODEL: str = "gpt-35-turbo"

    def __init__(
        self,
        model: str = "gpt-35-turbo",
        stream: bool = True,
        temperature: float = 0.7,
        context_length_control: str = "latest",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.model = model
        self.stream = stream
        self.temperature = temperature
        self.context_length_control = context_length_control

    def create_completion(
        self,
        messages: list = list,
        model: str | None = None,
        stream: bool | None = None,
        temperature: float | None = None,
        max_tokens: int = 2048,
        tools: list | NotGiven = NOT_GIVEN,
        tool_choice: str | NotGiven = NOT_GIVEN,
    ):
        if model is not None:
            self.model = model
        if stream is not None:
            self.stream = stream
        if temperature is not None:
            self.temperature = temperature
        if self.context_length_control == "latest":
            messages = cutoff_messages(messages, max_count=MODEL_MAX_INPUT_LENGTH[self.model], model=self.model)

        self.client, model_id = get_openai_client_and_model(is_async=False, model_id=self.model)

        response: ChatCompletion | Stream[ChatCompletionChunk] = self.client.chat.completions.create(
            model=model_id,
            messages=messages,
            stream=self.stream,
            temperature=self.temperature,
            max_tokens=max_tokens,
            tool_choice=tool_choice,
            tools=tools,
        )

        if self.stream:

            def generator():
                chunk_count = 0
                for chunk in response:
                    if len(chunk.choices) > 0:
                        chunk_count += 1
                        yield chunk.choices[0].delta.model_dump()

            return generator()
        else:
            result = {
                "content": response.choices[0].message.content,
                "usage": response.usage.model_dump(),
            }
            if response.choices[0].message.tool_calls:
                result["tool_calls"] = [tool_call.model_dump() for tool_call in response.choices[0].message.tool_calls]
            return result


class AsyncOpenAIChatClient(BaseAsyncChatClient):
    DEFAULT_MODEL: str = "gpt-35-turbo"

    def __init__(
        self,
        model: str = "gpt-35-turbo",
        stream: bool = True,
        temperature: float = 0.7,
        context_length_control: str = "latest",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.model = model
        self.stream = stream
        self.temperature = temperature
        self.context_length_control = context_length_control

    async def create_completion(
        self,
        messages: list = list,
        model: str | None = None,
        stream: bool | None = None,
        temperature: float | None = None,
        max_tokens: int = 2048,
        tools: list | NotGiven = NOT_GIVEN,
        tool_choice: str | NotGiven = NOT_GIVEN,
    ) -> Union[AsyncGenerator[str, None], str]:
        if model is not None:
            self.model = model
        if stream is not None:
            self.stream = stream
        if temperature is not None:
            self.temperature = temperature
        if self.context_length_control == "latest":
            messages = cutoff_messages(messages, max_count=MODEL_MAX_INPUT_LENGTH[self.model], model=self.model)

        self.client, model_id = get_openai_client_and_model(is_async=True, model_id=self.model)

        response: ChatCompletion | AsyncStream[ChatCompletionChunk] = await self.client.chat.completions.create(
            model=model_id,
            messages=messages,
            stream=self.stream,
            temperature=self.temperature,
            max_tokens=max_tokens,
            tool_choice=tool_choice,
            tools=tools,
        )

        if self.stream:

            async def generator():
                async for chunk in response:
                    if len(chunk.choices) > 0:
                        yield chunk.choices[0].delta.model_dump()

            return generator()
        else:
            result = {
                "content": response.choices[0].message.content,
                "usage": response.usage.model_dump(),
            }
            if response.choices[0].message.tool_calls:
                result["tool_calls"] = [tool_call.model_dump() for tool_call in response.choices[0].message.tool_calls]
            return result
