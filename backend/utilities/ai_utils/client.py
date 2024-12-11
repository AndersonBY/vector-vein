from typing import overload, Tuple, Literal, Union

from openai import AsyncOpenAI, OpenAI, AsyncAzureOpenAI, AzureOpenAI

from vectorvein.types.enums import BackendType
from vectorvein.settings import settings as vectorvein_settings
from vectorvein.chat_clients import create_chat_client, create_async_chat_client

from utilities.config import Settings


@overload
def get_openai_client_and_model_id(
    is_async: Literal[False], model_id: str = ""
) -> Tuple[OpenAI | AzureOpenAI, str]: ...


@overload
def get_openai_client_and_model_id(
    is_async: Literal[True], model_id: str = ""
) -> Tuple[AsyncOpenAI | AsyncAzureOpenAI, str]: ...


def get_openai_client_and_model_id(
    is_async: bool = False,
    model_id: str = "",
) -> Tuple[Union[OpenAI, AsyncOpenAI, AzureOpenAI, AsyncAzureOpenAI], str]:
    user_settings = Settings()
    vectorvein_settings.load(user_settings.get("llm_settings"))
    if is_async:
        client = create_async_chat_client(backend=BackendType.OpenAI, model=model_id, stream=False)
    else:
        client = create_chat_client(backend=BackendType.OpenAI, model=model_id, stream=False)

    model = client.backend_settings.models[model_id].id
    return client.raw_client, model
