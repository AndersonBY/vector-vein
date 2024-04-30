# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-12-12 15:23:26
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-04-30 15:52:44
from typing import Union, AsyncGenerator

import httpx
from openai import OpenAI, AsyncOpenAI
from openai import AzureOpenAI, AsyncAzureOpenAI
from openai._streaming import Stream, AsyncStream
from openai._types import NotGiven, NOT_GIVEN
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from utilities.settings import Settings
from utilities.web_crawler import proxies
from .base_client import BaseChatClient, BaseAsyncChatClient
from .utils import cutoff_messages


MODEL_MAX_INPUT_LENGTH = {
    "gpt-35-turbo": 16385,
    "gpt-4": 128000,
}


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
        self.settings = Settings()
        self.openai_api_type = self.settings.openai_api_type
        if self.openai_api_type == "azure":
            self.client = AzureOpenAI(
                azure_endpoint=self.settings.azure_endpoint,
                api_key=self.settings.azure_api_key,
                api_version="2024-03-01-preview",
                http_client=httpx.Client(
                    proxies=proxies(),
                    transport=httpx.HTTPTransport(local_address="0.0.0.0"),
                ),
            )

        else:
            self.client = OpenAI(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.get("openai_api_base", "https://api.openai.com/v1"),
                http_client=httpx.Client(
                    proxies=proxies(),
                    transport=httpx.HTTPTransport(local_address="0.0.0.0"),
                ),
            )

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
            messages = cutoff_messages(messages, max_count=MODEL_MAX_INPUT_LENGTH[self.model])

        if self.openai_api_type == "azure":
            if self.model == "gpt-3.5":
                model_id = self.settings.azure_gpt_35_deployment_id
            elif self.model == "gpt-4":
                model_id = self.settings.azure_gpt_4_deployment_id
            else:
                model_id = self.model
        else:
            model_id = self.model

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
        self.settings = Settings()
        self.openai_api_type = self.settings.openai_api_type
        if self.openai_api_type == "azure":
            self.client = AsyncAzureOpenAI(
                azure_endpoint=self.settings.azure_endpoint,
                api_key=self.settings.azure_api_key,
                api_version="2024-03-01-preview",
                http_client=httpx.Client(
                    proxies=proxies(),
                    transport=httpx.HTTPTransport(local_address="0.0.0.0"),
                ),
            )

        else:
            self.client = AsyncOpenAI(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.get("openai_api_base", "https://api.openai.com/v1"),
                http_client=httpx.Client(
                    proxies=proxies(),
                    transport=httpx.HTTPTransport(local_address="0.0.0.0"),
                ),
            )

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
            messages = cutoff_messages(messages, max_count=MODEL_MAX_INPUT_LENGTH[self.model])

        if self.openai_api_type == "azure":
            if self.model == "gpt-3.5":
                model_id = self.settings.azure_gpt_35_deployment_id
            elif self.model == "gpt-4":
                model_id = self.settings.azure_gpt_4_deployment_id
            else:
                model_id = self.model
        else:
            model_id = self.model

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
                chunk_count = 0
                async for chunk in response:
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
