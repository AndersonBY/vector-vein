from vectorvein.types.enums import BackendType
from vectorvein.settings import settings as vectorvein_settings
from vectorvein.chat_clients import create_chat_client, create_async_chat_client

from utilities.config import Settings


def get_openai_client_and_model_id(
    is_async: bool = False,
    model_id: str = "",
):
    user_settings = Settings()
    vectorvein_settings.load(user_settings.get("llm_settings"))
    if is_async:
        client = create_async_chat_client(backend=BackendType.OpenAI, model=model_id, stream=False)
    else:
        client = create_chat_client(backend=BackendType.OpenAI, model=model_id, stream=False)

    model = client.backend_settings.models[model_id].id
    return client.raw_client, model
