# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-12-12 15:24:15
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-18 01:29:29
import json
from typing import Union, AsyncGenerator

from openai import OpenAI, AsyncOpenAI
from openai._types import NotGiven, NOT_GIVEN
from openai._streaming import Stream, AsyncStream
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from utilities.config import Settings
from .base_client import BaseChatClient, BaseAsyncChatClient
from .utils import (
    tool_use_re,
    cutoff_messages,
    generate_tool_use_system_prompt,
    extract_tool_calls,
)


class OpenAICompatibleChatClient(BaseChatClient):
    DEFAULT_MODEL: str = ""
    MODEL_MAX_INPUT_LENGTH: dict[str, int] = {}
    MODEL_FUNCTION_CALLING_AVAILABLE: dict[str, bool] = {}
    API_KEY_SETTING_NAME: str = ""
    API_BASE_SETTING_NAME: str = ""

    def __init__(
        self,
        model: str = "",
        stream: bool = True,
        temperature: float = 0.7,
        context_length_control: str = "latest",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.model = model or self.DEFAULT_MODEL
        self.stream = stream
        self.temperature = temperature
        self.context_length_control = context_length_control
        settings = Settings()
        self._client = OpenAI(
            api_key=settings.get(self.API_KEY_SETTING_NAME),
            base_url=settings.get(self.API_BASE_SETTING_NAME),
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
            messages = cutoff_messages(messages, max_count=self.MODEL_MAX_INPUT_LENGTH[self.model], model=self.model)

        if tools:
            if self.MODEL_FUNCTION_CALLING_AVAILABLE[self.model]:
                tools_params = dict(tools=tools, tool_choice=tool_choice)
            else:
                tools_str = json.dumps(tools, ensure_ascii=False, indent=None)
                additional_system_prompt = generate_tool_use_system_prompt(tools=tools_str)
                if messages and messages[0].get("role") == "system":
                    messages[0]["content"] += "\n\n" + additional_system_prompt
                else:
                    messages.insert(0, {"role": "system", "content": additional_system_prompt})
                tools_params = {}
        else:
            tools_params = {}

        response: ChatCompletion | Stream[ChatCompletionChunk] = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=self.stream,
            temperature=self.temperature,
            max_tokens=max_tokens,
            **tools_params,
        )

        if self.stream:

            def generator():
                full_content = ""
                result = {}
                for chunk in response:
                    if len(chunk.choices) == 0:
                        continue
                    if self.MODEL_FUNCTION_CALLING_AVAILABLE[self.model]:
                        yield chunk.choices[0].delta.model_dump()
                    else:
                        message = chunk.choices[0].delta.model_dump()
                        full_content += message["content"] if message["content"] else ""
                        if tools:
                            tool_call_data = extract_tool_calls(full_content)
                            if tool_call_data:
                                message["tool_calls"] = tool_call_data["tool_calls"]
                        if full_content in ("<", "<|", "<|▶", "<|▶|") or full_content.startswith("<|▶|>"):
                            message["content"] = ""
                            result = message
                            continue
                        yield message
                if result:
                    yield result

            return generator()
        else:
            result = {
                "content": response.choices[0].message.content,
                "usage": response.usage.model_dump(),
            }
            if tools:
                tool_call_data = extract_tool_calls(result["content"])
                if tool_call_data:
                    result["tool_calls"] = tool_call_data["tool_calls"]
                    result["content"] = tool_use_re.sub("", result["content"])
            return result


class AsyncOpenAICompatibleChatClient(BaseAsyncChatClient):
    DEFAULT_MODEL: str = ""
    MODEL_MAX_INPUT_LENGTH: dict[str, int] = {}
    MODEL_FUNCTION_CALLING_AVAILABLE: dict[str, bool] = {}
    API_KEY_SETTING_NAME: str = ""
    API_BASE_SETTING_NAME: str = ""

    def __init__(
        self,
        model: str = "",
        stream: bool = True,
        temperature: float = 0.7,
        context_length_control: str = "latest",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.model = model or self.DEFAULT_MODEL
        self.stream = stream
        self.temperature = temperature
        self.context_length_control = context_length_control
        settings = Settings()
        self._client = AsyncOpenAI(
            api_key=settings.get(self.API_KEY_SETTING_NAME),
            base_url=settings.get(self.API_BASE_SETTING_NAME),
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
            messages = cutoff_messages(messages, max_count=self.MODEL_MAX_INPUT_LENGTH[self.model], model=self.model)

        if tools:
            if self.MODEL_FUNCTION_CALLING_AVAILABLE[self.model]:
                tools_params = dict(tools=tools, tool_choice=tool_choice)
            else:
                tools_str = json.dumps(tools, ensure_ascii=False, indent=None)
                additional_system_prompt = generate_tool_use_system_prompt(tools=tools_str)
                if messages and messages[0].get("role") == "system":
                    messages[0]["content"] += "\n\n" + additional_system_prompt
                else:
                    messages.insert(0, {"role": "system", "content": additional_system_prompt})
                tools_params = {}
        else:
            tools_params = {}

        response: ChatCompletion | AsyncStream[ChatCompletionChunk] = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=self.stream,
            temperature=self.temperature,
            max_tokens=max_tokens,
            **tools_params,
        )

        if self.stream:

            async def generator():
                full_content = ""
                result = {}
                async for chunk in response:
                    if len(chunk.choices) == 0:
                        continue
                    if self.MODEL_FUNCTION_CALLING_AVAILABLE[self.model]:
                        yield chunk.choices[0].delta.model_dump()
                    else:
                        message = chunk.choices[0].delta.model_dump()
                        full_content += message["content"] if message["content"] else ""
                        if tools:
                            tool_call_data = extract_tool_calls(full_content)
                            if tool_call_data:
                                message["tool_calls"] = tool_call_data["tool_calls"]
                        if full_content in ("<", "<|", "<|▶", "<|▶|") or full_content.startswith("<|▶|>"):
                            message["content"] = ""
                            result = message
                            continue
                        yield message
                if result:
                    yield result

            return generator()
        else:
            result = {
                "content": response.choices[0].message.content,
                "usage": response.usage.model_dump(),
            }
            if tools:
                tool_call_data = extract_tool_calls(result["content"])
                if tool_call_data:
                    result["tool_calls"] = tool_call_data["tool_calls"]
                    result["content"] = tool_use_re.sub("", result["content"])
            return result
