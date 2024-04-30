# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-12-12 15:24:15
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-04-30 20:47:19
from typing import Union, AsyncGenerator

from openai import OpenAI, AsyncOpenAI
from openai._streaming import Stream, AsyncStream
from openai._types import NotGiven, NOT_GIVEN
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from utilities.settings import Settings
from .base_client import BaseChatClient, BaseAsyncChatClient
from .utils import cutoff_messages


MODEL_MAX_INPUT_LENGTH = {
    "moonshot-v1-8k": 8000,
    "moonshot-v1-32k": 32000,
    "moonshot-v1-128k": 128000,
}


class MoonshotChatClient(BaseChatClient):
    DEFAULT_MODEL: str = "moonshot-v1-8k"

    def __init__(
        self,
        model: str = "moonshot-v1-8k",
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
        settings = Settings()
        self._client = OpenAI(
            api_key=settings.moonshot_api_key,
            base_url=settings.moonshot_api_base,
        )

    def create_completion(
        self,
        messages: list = list,
        model: str | None = None,
        stream: bool | None = None,
        temperature: float | None = None,
        max_tokens: int = 2000,
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

        response: ChatCompletion | Stream[ChatCompletionChunk] = self._client.chat.completions.create(
            model=self.model,
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


class AsyncMoonshotChatClient(BaseAsyncChatClient):
    DEFAULT_MODEL: str = "moonshot-v1-8k"

    def __init__(
        self,
        model: str = "moonshot-v1-8k",
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
        settings = Settings()
        self._client = AsyncOpenAI(
            api_key=settings.moonshot_api_key,
            base_url=settings.moonshot_api_base,
        )

    async def create_completion(
        self,
        messages: list = list,
        model: str | None = None,
        stream: bool | None = None,
        temperature: float | None = None,
        max_tokens: int = 2000,
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

        response: ChatCompletion | AsyncStream[ChatCompletionChunk] = await self._client.chat.completions.create(
            model=self.model,
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
