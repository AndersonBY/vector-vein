# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-12-12 15:24:15
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-04-30 15:05:16
import json

from anthropic import Anthropic, AsyncAnthropic
from anthropic._types import NotGiven, NOT_GIVEN
from anthropic.types import ContentBlockDeltaEvent

from utilities.settings import Settings
from .base_client import BaseChatClient, BaseAsyncChatClient
from .utils import (
    cutoff_messages,
    get_tool_call_data_in_openai_format,
    generate_tool_use_system_prompt,
    tool_use_re,
)


MODEL_MAX_INPUT_LENGTH = {
    "claude-3-opus-20240229": 200000,
    "claude-3-sonnet-20240229": 200000,
    "claude-3-haiku-20240307": 200000,
}


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
            base_url=settings.anthropic_base_url,
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
            messages = cutoff_messages(messages, max_count=MODEL_MAX_INPUT_LENGTH[self.model])

        messages = format_messages_alternate(messages)

        if tools:
            tools_str = json.dumps(tools, ensure_ascii=False, indent=None)
            system_prompt += "\n\n" + generate_tool_use_system_prompt(tools=tools_str, format_type="anthropic")

        response = self._client.messages.create(
            model=self.model,
            messages=messages,
            system=system_prompt,
            stream=self.stream,
            temperature=self.temperature,
            max_tokens=max_tokens,
        )

        if self.stream:

            def generator():
                chunk_count = 0
                full_content = ""
                result = {}
                for chunk in response:
                    if not isinstance(chunk, ContentBlockDeltaEvent):
                        continue

                    chunk_count += 1
                    message = {"content": chunk.delta.text}
                    full_content += message["content"] if message["content"] else ""
                    if tools:
                        tool_call_data = get_tool_call_data_in_openai_format(
                            full_content, input_format="anthropic", tools=tools
                        )
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
                "content": response.content[0].text,
                "usage": {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                },
            }
            if tools:
                tool_call_data = get_tool_call_data_in_openai_format(
                    result["content"], input_format="anthropic", tools=tools
                )
                if tool_call_data:
                    result["tool_calls"] = tool_call_data["tool_calls"]
                    result["content"] = tool_use_re.sub("", result["content"])
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
            base_url=settings.anthropic_base_url,
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
            messages = cutoff_messages(messages, max_count=MODEL_MAX_INPUT_LENGTH[self.model])

        messages = format_messages_alternate(messages)

        if tools:
            tools_str = json.dumps(tools, ensure_ascii=False, indent=None)
            system_prompt += "\n\n" + generate_tool_use_system_prompt(tools=tools_str, format_type="anthropic")

        response = await self._client.messages.create(
            model=self.model,
            messages=messages,
            system=system_prompt,
            stream=self.stream,
            temperature=self.temperature,
            max_tokens=max_tokens,
        )

        if self.stream:

            async def generator():
                chunk_count = 0
                full_content = ""
                result = {}
                async for chunk in response:
                    if not isinstance(chunk, ContentBlockDeltaEvent):
                        continue

                    chunk_count += 1
                    message = {"content": chunk.delta.text}
                    full_content += message["content"] if message["content"] else ""
                    if tools:
                        tool_call_data = get_tool_call_data_in_openai_format(
                            full_content, input_format="anthropic", tools=tools
                        )
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
                "content": response.content[0].text,
                "usage": {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                },
            }
            if tools:
                tool_call_data = get_tool_call_data_in_openai_format(
                    result["content"], input_format="anthropic", tools=tools
                )
                if tool_call_data:
                    result["tool_calls"] = tool_call_data["tool_calls"]
                    result["content"] = tool_use_re.sub("", result["content"])
            return result
