# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-16 18:15:11
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-24 15:32:02
import httpx

from utilities.config import Settings
from utilities.network import proxies
from .chat_clients.openai_client import get_openai_client_and_model


class EmbeddingClient:
    def __init__(self, provider: str, model_id: str, dimensions: int | None = None) -> None:
        self.provider = provider
        self.model_id = model_id
        self.dimensions = dimensions

        setting = Settings()
        if provider == "openai":
            self.client, self.model_id = get_openai_client_and_model(is_async=False, model_id=model_id)
        elif provider == "text-embeddings-inference":
            # https://github.com/huggingface/text-embeddings-inference
            self.api_base = setting.get(
                "embedding_models.text_embeddings_inference.api_base", "http://localhost:8080/embed"
            )
            self.api_key = setting.get("embedding_models.text_embeddings_inference.api_key")

    def get(self, input: str | list) -> list:
        if self.provider == "openai":
            if self.dimensions and self.model_id != "text-embedding-ada-002":
                dimensions_params = {"dimensions": self.dimensions}
            else:
                dimensions_params = {}
            response = self.client.embeddings.create(input=input, model=self.model_id, **dimensions_params)
            if isinstance(input, str):
                return response.data[0].embedding
            else:
                return [item.embedding for item in response.data]
        elif self.provider == "text-embeddings-inference":
            if self.api_key:
                headers = {"Authorization": f"Bearer {self.api_key}"}
            else:
                headers = None
            response = httpx.post(
                self.api_base, headers=headers, json={"inputs": input}, proxies=proxies(), timeout=60 * 60
            )
            result = response.json()
            if isinstance(input, str):
                return result[0]
            else:
                return result
