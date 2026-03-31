# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-16 18:15:11
from collections.abc import Sequence

from vv_llm.embedding_clients import create_embedding_client
from vv_llm.settings import settings as vv_llm_settings

from utilities.config import Settings


LEGACY_TEI_PROVIDER = "text-embeddings-inference"
LEGACY_TEI_MODEL = "text-embeddings-inference"


class EmbeddingClient:
    def __init__(self, provider: str, model_id: str, dimensions: int | None = None) -> None:
        self.provider, self.model_id = self._normalize_provider_and_model(provider, model_id)
        self.dimensions = dimensions

        user_settings = Settings()
        vv_llm_settings.load(user_settings.get("llm_settings"))
        self.client = create_embedding_client(
            backend=self.provider,
            model=self.model_id or None,
            settings=vv_llm_settings,
        )

    @staticmethod
    def _normalize_provider_and_model(provider: str, model_id: str) -> tuple[str, str]:
        normalized_provider = provider.strip().lower()
        normalized_model = model_id.strip()

        if normalized_provider == LEGACY_TEI_PROVIDER:
            return "custom", LEGACY_TEI_MODEL

        return normalized_provider, normalized_model

    def get(self, input: str | Sequence[str]) -> list[float] | list[list[float]]:
        if isinstance(input, str):
            return self.client.embed(input, dimensions=self.dimensions)

        return self.client.embed_batch(list(input), dimensions=self.dimensions)
