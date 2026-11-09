import math

from vv_llm.rerank_clients import create_rerank_client
from vv_llm.retrieval_clients.common import extract_json_path
from vv_llm.settings import Settings as LlmSettings

from utilities.config import Settings
from utilities.config.settings import validate_rerank_settings


class Reranker:
    def __init__(self, client):
        self.client = client

    def rerank(self, **kwargs):
        response = self.client.rerank(**kwargs)
        # vv-llm coerces indices/scores and supplies missing fields. Validate the
        # original response too, before those defaults can hide malformed output.
        raw = response.raw_response
        model = self.client.model_setting
        custom = model.protocol == "custom_json_http" or (
            model.protocol is None and self.client.backend_name in {"custom", "local", "openai"})
        mapping = model.response_mapping if custom else None
        if mapping and mapping.results_path:
            items = extract_json_path(raw, mapping.results_path)
        else:
            items = raw.get("results", raw.get("data"))
        if not isinstance(items, list) or not items:
            raise ValueError("Invalid rerank results")
        fields = mapping.field_map if mapping else {}
        seen = set()
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Invalid rerank result")
            index_path = fields.get("index")
            score_path = fields.get("relevance_score")
            index = (extract_json_path(item, index_path if index_path.startswith("$") else f"$.{index_path}")
                     if index_path else item.get("index"))
            score = (extract_json_path(item, score_path if score_path.startswith("$") else f"$.{score_path}") if score_path
                     else item.get("relevance_score", item.get("score")))
            if (type(index) is not int or not 0 <= index < len(kwargs["documents"]) or index in seen
                    or isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score)):
                raise ValueError("Invalid rerank index or score")
            seen.add(index)
        return response


def configured_reranker():
    settings = Settings()
    provider, model = validate_rerank_settings(settings.data)
    if not provider:
        return None
    # Each search owns its settings snapshot; concurrent settings loads cannot reroute it.
    return Reranker(create_rerank_client(
        backend=provider, model=model,
        settings=LlmSettings.model_validate(settings.get("llm_settings")),
    ))
