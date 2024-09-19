# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-12-12 15:38:43
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-24 14:59:24
from vectorvein.types.enums import BackendType
from vectorvein.settings import settings as vectorvein_settings
from vectorvein.chat_clients import create_chat_client, create_async_chat_client
from vectorvein.chat_clients.utils import get_token_counts, format_messages, cutoff_messages, ToolCallContentProcessor

from utilities.config import Settings
from .agent import ToolCallData
from .embeddings import EmbeddingClient
from .client import get_openai_client_and_model_id


def conversation_title_generator(
    messages: list, max_input_length: int = 512, backend: BackendType = BackendType.OpenAI, model: str = "gpt-4o-mini"
):
    user_settings = Settings()
    vectorvein_settings.load(user_settings.get("llm_settings"))
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
    summary = client.create_completion(messages).content
    return summary


__all__ = [
    "ToolCallData",
    "EmbeddingClient",
    "format_messages",
    "cutoff_messages",
    "get_token_counts",
    "create_chat_client",
    "create_async_chat_client",
    "ToolCallContentProcessor",
    "conversation_title_generator",
    "get_openai_client_and_model_id",
]
