# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-12-12 15:22:52
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-02-26 19:20:44
class BaseChatClient:
    DEFAULT_MODEL: str | None = None

    def __init__(
        self,
        model: str = "gpt-35-turbo",
        stream: bool = True,
        temperature: float = 0.7,
        context_length_control: str = "latest",
    ):
        self.model = model
        self.stream = stream
        self.temperature = temperature
        self.context_length_control = context_length_control
        self.is_async = False

    def create_completion(
        self,
        messages: list,
        model: str | None = None,
        stream: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        tools: list | None = None,
        tool_choice: str | None = None,
    ):
        raise NotImplementedError("Subclasses should implement this method")


class BaseAsyncChatClient:
    def __init__(
        self,
        model: str = "gpt-35-turbo",
        stream: bool = True,
        temperature: float = 0.7,
        context_length_control: str = "latest",
    ):
        self.model = model
        self.stream = stream
        self.temperature = temperature
        self.context_length_control = context_length_control
        self.is_async = True

    async def create_completion(
        self,
        model: str | None = None,
        stream: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        tools: list | None = None,
        tool_choice: str | None = None,
    ):
        raise NotImplementedError("Subclasses should implement this method")
