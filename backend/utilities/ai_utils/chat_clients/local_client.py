# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-12-12 15:24:15
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-28 03:20:15
import json

from openai import OpenAI, AsyncOpenAI
from openai._types import NotGiven, NOT_GIVEN
from openai._streaming import Stream, AsyncStream
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from utilities.config import Settings
from .base_client import BaseChatClient, BaseAsyncChatClient
from .utils import (
    tool_use_re,
    cutoff_messages,
    extract_tool_calls,
    generate_tool_use_system_prompt,
)


class LocalChatClient(BaseChatClient):
    DEFAULT_MODEL: str = ""

    def __init__(
        self,
        family: str,
        model: str = "",
        stream: bool = True,
        temperature: float = 0.7,
        context_length_control: str = "latest",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.family = family.lower()
        self.model = model
        self.stream = stream
        self.temperature = temperature
        self.context_length_control = context_length_control
        settings = Settings()
        self.family_settings = next(
            (item for item in settings.local_llms if item["model_family"].lower() == family), None
        )
        self._client = OpenAI(
            api_key=self.family_settings["api_key"],
            base_url=self.family_settings["api_base"],
        )
        self._native_function_calling_available = False

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

        self.model_settings = next(
            (item for item in self.family_settings["models"] if item["model_id"].lower() == self.model.lower()), None
        )

        self._native_function_calling_available = self.model_settings.get("function_calling", False)

        if self.context_length_control == "latest":
            messages = cutoff_messages(messages, max_count=self.model_settings["max_tokens"])

        if tools:
            if self._native_function_calling_available:
                tools_params = dict(tools=tools, tool_choice=tool_choice)
            else:
                tools_str = json.dumps(tools, ensure_ascii=False, indent=None)
                additional_system_prompt = generate_tool_use_system_prompt(tools=tools_str)
                if messages[0].get("role") == "system":
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
                    if self._native_function_calling_available:
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


class AsyncLocalChatClient(BaseAsyncChatClient):
    DEFAULT_MODEL: str = ""

    def __init__(
        self,
        family: str,
        model: str = "",
        stream: bool = True,
        temperature: float = 0.7,
        context_length_control: str = "latest",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.family = family.lower()
        self.model = model
        self.stream = stream
        self.temperature = temperature
        self.context_length_control = context_length_control
        settings = Settings()
        self.family_settings = next(
            (item for item in settings.local_llms if item["model_family"].lower() == family), None
        )
        self._client = AsyncOpenAI(
            api_key=self.family_settings["api_key"],
            base_url=self.family_settings["api_base"],
        )
        self._native_function_calling_available = False

    async def create_completion(
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

        self.model_settings = next(
            (item for item in self.family_settings["models"] if item["model_id"].lower() == self.model.lower()), None
        )

        self._native_function_calling_available = self.model_settings.get("function_calling", False)

        if self.context_length_control == "latest":
            messages = cutoff_messages(messages, max_count=self.model_settings["max_tokens"])

        if tools:
            if self._native_function_calling_available:
                tools_params = dict(tools=tools, tool_choice=tool_choice)
            else:
                tools_str = json.dumps(tools, ensure_ascii=False, indent=None)
                additional_system_prompt = generate_tool_use_system_prompt(tools=tools_str)
                if messages[0].get("role") == "system":
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
                    if self._native_function_calling_available:
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
