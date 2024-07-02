# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-12-12 15:24:15
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-07-02 17:37:48
import json

from anthropic import Anthropic, AsyncAnthropic
from anthropic._types import NotGiven, NOT_GIVEN
from anthropic.types import (
    ToolUseBlock,
    TextBlock,
    RawMessageStartEvent,
    RawContentBlockStartEvent,
    RawContentBlockDeltaEvent,
    RawMessageDeltaEvent,
)

from utilities.config import Settings
from .base_client import BaseChatClient, BaseAsyncChatClient
from .utils import cutoff_messages


MODEL_MAX_INPUT_LENGTH = {
    "claude-3-opus-20240229": 200000,
    "claude-3-sonnet-20240229": 200000,
    "claude-3-haiku-20240307": 200000,
    "claude-3-5-sonnet-20240620": 200000,
}


def refactor_tool_use_params(tools: list):
    return [
        {
            "name": tool["function"]["name"],
            "description": tool["function"]["description"],
            "input_schema": tool["function"]["parameters"],
        }
        for tool in tools
    ]


def refactor_tool_calls(tool_calls: list):
    return [
        {
            "index": index,
            "id": tool["id"],
            "type": "function",
            "function": {
                "name": tool["name"],
                "arguments": json.dumps(tool["input"], ensure_ascii=False),
            },
        }
        for index, tool in enumerate(tool_calls)
    ]


def format_messages_alternate(messages: list) -> list:
    # messages: roles must alternate between "user" and "assistant", and not multiple "user" roles in a row
    # reformat multiple "user" roles in a row into {"role": "user", "content": [{"type": "text", "text": "Hello, Claude"}, {"type": "text", "text": "How are you?"}]}
    # same for assistant role
    # if not multiple "user" or "assistant" roles in a row, keep it as is

    formatted_messages = []
    current_role = None
    current_content = []

    for message in messages:
        role = message["role"]
        content = message["content"]

        if role != current_role:
            if current_content:
                formatted_messages.append({"role": current_role, "content": current_content})
                current_content = []
            current_role = role

        if isinstance(content, str):
            current_content.append({"type": "text", "text": content})
        elif isinstance(content, list):
            current_content.extend(content)
        else:
            current_content.append(content)

    if current_content:
        formatted_messages.append({"role": current_role, "content": current_content})

    return formatted_messages


class AnthropicChatClient(BaseChatClient):
    DEFAULT_MODEL: str = "claude-3-sonnet-20240229"

    def __init__(
        self,
        model: str = "claude-3-sonnet-20240229",
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
        self._client = Anthropic(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_api_base,
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

        if messages[0].get("role") == "system":
            system_prompt = messages[0]["content"]
            messages = messages[1:]
        else:
            system_prompt = ""

        if self.context_length_control == "latest":
            messages = cutoff_messages(messages, max_count=MODEL_MAX_INPUT_LENGTH[self.model], model=self.model)

        messages = format_messages_alternate(messages)

        response = self._client.messages.create(
            model=self.model,
            messages=messages,
            system=system_prompt,
            stream=self.stream,
            temperature=self.temperature,
            max_tokens=max_tokens,
            tools=refactor_tool_use_params(tools) if tools else tools,
            tool_choice=tool_choice,
        )

        if self.stream:

            def generator():
                result = {"content": ""}
                for chunk in response:
                    message = {"content": ""}
                    if isinstance(chunk, RawMessageStartEvent):
                        result["usage"] = {"prompt_tokens": chunk.message.usage.input_tokens}
                        continue
                    elif isinstance(chunk, RawContentBlockStartEvent):
                        if chunk.content_block.type == "tool_use":
                            result["tool_calls"] = message["tool_calls"] = [
                                {
                                    "index": 0,
                                    "id": chunk.content_block.id,
                                    "function": {
                                        "arguments": "",
                                        "name": chunk.content_block.name,
                                    },
                                    "type": "function",
                                }
                            ]
                        elif chunk.content_block.type == "text":
                            message["content"] = chunk.content_block.text
                        yield message
                    elif isinstance(chunk, RawContentBlockDeltaEvent):
                        if chunk.delta.type == "text_delta":
                            message["content"] = chunk.delta.text
                            result["content"] += chunk.delta.text
                        elif chunk.delta.type == "input_json_delta":
                            result["tool_calls"][0]["function"]["arguments"] += chunk.delta.partial_json
                            message["tool_calls"] = [
                                {
                                    "index": 0,
                                    "id": result["tool_calls"][0]["id"],
                                    "function": {
                                        "arguments": chunk.delta.partial_json,
                                        "name": result["tool_calls"][0]["function"]["name"],
                                    },
                                    "type": "function",
                                }
                            ]
                        yield message
                    elif isinstance(chunk, RawMessageDeltaEvent):
                        result["usage"]["completion_tokens"] = chunk.usage.output_tokens
                        result["usage"]["total_tokens"] = (
                            result["usage"]["prompt_tokens"] + result["usage"]["completion_tokens"]
                        )
                        yield {"usage": result["usage"]}

            return generator()
        else:
            result = {
                "content": "",
                "usage": {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                },
            }
            tool_calls = []
            for content_block in response.content:
                if isinstance(content_block, TextBlock):
                    result["content"] += content_block.text
                elif isinstance(content_block, ToolUseBlock):
                    tool_calls.append(content_block.model_dump())

            if tool_calls:
                result["tool_calls"] = refactor_tool_calls(tool_calls)

            return result


class AsyncAnthropicChatClient(BaseAsyncChatClient):
    DEFAULT_MODEL: str = "claude-3-sonnet-20240229"

    def __init__(
        self,
        model: str = "claude-3-sonnet-20240229",
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
        self._client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_api_base,
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
    ):
        if model is not None:
            self.model = model
        if stream is not None:
            self.stream = stream
        if temperature is not None:
            self.temperature = temperature

        if messages[0].get("role") == "system":
            system_prompt = messages[0]["content"]
            messages = messages[1:]
        else:
            system_prompt = ""

        if self.context_length_control == "latest":
            messages = cutoff_messages(messages, max_count=MODEL_MAX_INPUT_LENGTH[self.model], model=self.model)

        messages = format_messages_alternate(messages)

        response = await self._client.messages.create(
            model=self.model,
            messages=messages,
            system=system_prompt,
            stream=self.stream,
            temperature=self.temperature,
            max_tokens=max_tokens,
            tools=refactor_tool_use_params(tools) if tools else tools,
            tool_choice=tool_choice,
        )

        if self.stream:

            async def generator():
                result = {"content": ""}
                async for chunk in response:
                    message = {"content": ""}
                    if isinstance(chunk, RawMessageStartEvent):
                        result["usage"] = {"prompt_tokens": chunk.message.usage.input_tokens}
                        continue
                    elif isinstance(chunk, RawContentBlockStartEvent):
                        if chunk.content_block.type == "tool_use":
                            result["tool_calls"] = message["tool_calls"] = [
                                {
                                    "index": 0,
                                    "id": chunk.content_block.id,
                                    "function": {
                                        "arguments": "",
                                        "name": chunk.content_block.name,
                                    },
                                    "type": "function",
                                }
                            ]
                        elif chunk.content_block.type == "text":
                            message["content"] = chunk.content_block.text
                        yield message
                    elif isinstance(chunk, RawContentBlockDeltaEvent):
                        if chunk.delta.type == "text_delta":
                            message["content"] = chunk.delta.text
                            result["content"] += chunk.delta.text
                        elif chunk.delta.type == "input_json_delta":
                            result["tool_calls"][0]["function"]["arguments"] += chunk.delta.partial_json
                            message["tool_calls"] = [
                                {
                                    "index": 0,
                                    "id": result["tool_calls"][0]["id"],
                                    "function": {
                                        "arguments": chunk.delta.partial_json,
                                        "name": result["tool_calls"][0]["function"]["name"],
                                    },
                                    "type": "function",
                                }
                            ]
                        yield message
                    elif isinstance(chunk, RawMessageDeltaEvent):
                        result["usage"]["completion_tokens"] = chunk.usage.output_tokens
                        result["usage"]["total_tokens"] = (
                            result["usage"]["prompt_tokens"] + result["usage"]["completion_tokens"]
                        )
                        yield {"usage": result["usage"]}

            return generator()
        else:
            result = {
                "content": "",
                "usage": {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                },
            }
            tool_calls = []
            for content_block in response.content:
                if isinstance(content_block, TextBlock):
                    result["content"] += content_block.text
                elif isinstance(content_block, ToolUseBlock):
                    tool_calls.append(content_block.model_dump())

            if tool_calls:
                result["tool_calls"] = refactor_tool_calls(tool_calls)

            return result
