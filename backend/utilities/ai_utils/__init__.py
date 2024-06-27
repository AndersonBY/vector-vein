# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-12-12 15:38:43
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-24 14:59:24
import re

from .agent import ToolCallData
from .embeddings import EmbeddingClient
from .chat_clients.openai_client import get_openai_client_and_model
from .chat_clients import create_chat_client, create_async_chat_client
from .chat_clients.utils import get_token_counts, format_messages, cutoff_messages, tool_use_re


def contains_chinese(text):
    return re.search("[\u4e00-\u9fff]", text) is not None


def conversation_title_generator(
    messages: list, max_input_length: int = 512, backend: str = "OpenAI", model: str = "gpt-35-turbo"
):
    client = create_chat_client(backend=backend, model=model, stream=False)
    conversation_text = ""
    for message in messages:
        conversation_text += f'{message["role"]}:\n{message["content"]}\n\n'

    messages = [
        {
            "role": "system",
            "content": "You are a user dialogue title generator that can accurately distill and generate a title based on the provided dialogue content.",
        },
        {
            "role": "user",
            "content": f'Dialogue Content:\n\n{conversation_text[:max_input_length]}\n\n---\n\n# Objective\nGenerate a concise title based on the above dialogue content.\n\n# Requirements\n- Within 20 letters\n- Directly output the bare title text without explanation and decoration\n- No need to enclose with quotation marks\n- Do not start with "\n- The output language must be consistent with the dialogue language\n\n# Output Title',
        },
    ]
    summary = client.create_completion(messages)["content"]
    return summary


__all__ = [
    "tool_use_re",
    "ToolCallData",
    "EmbeddingClient",
    "format_messages",
    "cutoff_messages",
    "contains_chinese",
    "get_token_counts",
    "create_chat_client",
    "create_async_chat_client",
    "conversation_title_generator",
    "get_openai_client_and_model",
]
