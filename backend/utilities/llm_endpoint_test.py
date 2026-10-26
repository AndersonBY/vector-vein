"""One non-streaming request using only an endpoint editor's submitted draft."""
from copy import deepcopy
import math
import time
from urllib.parse import urlsplit

import httpx2
from anthropic import AnthropicBedrock
from openai import OpenAI, Omit
from pydantic import ValidationError
from vv_llm.chat_clients import create_chat_client
from vv_llm.settings import Settings as LlmSettings
from vv_llm.types import BackendType, EndpointSetting


REQUEST_TIMEOUT = 20.0


def run_model_endpoint_test(payload):
    if not isinstance(payload, dict):
        raise ValueError("Test parameters must be an object.")
    backend = payload.get("backend")
    if isinstance(backend, str) and backend.startswith("_local__"):
        backend = "local"
    try:
        backend = BackendType(backend)
    except (ValueError, TypeError):
        raise ValueError("Select a supported model backend.") from None
    model = payload.get("model_id")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Model ID is required.")
    model = model.strip()
    message = payload.get("message", "Hi!")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Test message cannot be blank.")
    if len(message) > 8000:
        raise ValueError("Test message must be at most 8000 characters.")
    draft = payload.get("endpoint")
    if not isinstance(draft, dict):
        raise ValueError("Select an endpoint to test.")
    try:
        endpoint = EndpointSetting.model_validate(deepcopy(draft))
    except ValidationError:
        raise ValueError("Invalid endpoint configuration.") from None
    if not endpoint.id.strip():
        raise ValueError("Endpoint ID is required.")
    if not endpoint.api_base or not endpoint.api_base.strip():
        raise ValueError("Endpoint API base URL is required.")
    endpoint.api_base = endpoint.api_base.strip()
    try:
        url = urlsplit(endpoint.api_base)
        if url.scheme not in {"http", "https"} or not url.hostname:
            raise ValueError
        url.port
    except ValueError:
        raise ValueError("Endpoint API base must be a valid HTTP or HTTPS URL.") from None

    # Normalize adapter flags with vv-llm before validating native credentials.
    endpoint.enabled = True
    settings = LlmSettings(
        endpoints=[endpoint.model_dump()],
        backends={backend.value: {"default_endpoint": endpoint.id, "models": {
            model: {"id": model, "endpoints": [endpoint.id]},
        }}},
    )
    endpoint = settings.get_endpoint(endpoint.id)
    adapter = endpoint.endpoint_type or "default"
    if adapter.startswith("anthropic") and backend != BackendType.Anthropic:
        raise ValueError("Anthropic endpoint adapters require the Anthropic backend.")
    native_anthropic = backend == BackendType.Anthropic and not adapter.startswith("openai")
    if adapter == "openai_azure" or (native_anthropic and adapter in {"default", "anthropic"}):
        if not endpoint.api_key or not endpoint.api_key.strip():
            raise ValueError("This endpoint requires an explicit API key.")
    if adapter in {"openai_vertex", "anthropic_vertex"}:
        expiry = endpoint.access_token_expires_at
        if not (endpoint.credentials and endpoint.credentials.get("quota_project_id")
                and endpoint.region and endpoint.access_token and expiry
                and math.isfinite(expiry) and expiry > time.time() + 300 + REQUEST_TIMEOUT):
            raise ValueError("Vertex testing requires explicit credentials, project, region and a current access token with expiry.")
    if adapter == "anthropic_bedrock":
        credentials = endpoint.credentials or {}
        if not (credentials.get("access_key") and credentials.get("secret_key") and endpoint.region):
            raise ValueError("Bedrock testing requires explicit access key, secret key and region.")

    anonymous = not endpoint.api_key
    if anonymous:
        # The SDK requires a nonempty construction key; clear it before any request.
        endpoint.api_key = "endpoint-test-anonymous"
    with httpx2.Client(proxy=endpoint.proxy, timeout=REQUEST_TIMEOUT, trust_env=False) as http_client:
        client = create_chat_client(
            backend=backend, model=model, stream=False, random_endpoint=False,
            endpoint_id=endpoint.id, settings=settings, http_client=http_client,
        )
        if adapter == "anthropic_bedrock":
            # vv-llm's Bedrock constructor also reads the ambient bearer token.
            client.endpoint, client.model_id = client._set_endpoint()
            raw = AnthropicBedrock(api_key="", base_url=endpoint.api_base,
                                   aws_region=endpoint.region, http_client=http_client)
            raw.aws_access_key = endpoint.credentials["access_key"]
            raw.aws_secret_key = endpoint.credentials["secret_key"]
        else:
            raw = client.raw_client
        raw.max_retries = 0
        raw.timeout = REQUEST_TIMEOUT
        if native_anthropic and adapter in {"default", "anthropic"}:
            # Anthropic SDK paths already include /v1; saved bases may include it too.
            raw.base_url = endpoint.api_base.rstrip("/").removesuffix("/v1")
        # SDK constructors also read ambient headers and account metadata.
        raw._custom_headers = {}
        if isinstance(raw, OpenAI):
            raw.api_key = "" if anonymous and adapter != "openai_vertex" else raw.api_key
            raw.admin_api_key = None
            raw.organization = None
            raw.project = None
            raw._azure_ad_token = None
            raw._azure_ad_token_provider = None
        if adapter == "anthropic_bedrock":
            raw.api_key = None
            raw.aws_session_token = (endpoint.credentials or {}).get("session_token") or ""
        headers = client._resolve_request_headers()
        if isinstance(raw, OpenAI) and not raw.api_key and not any(
            key.lower() == "authorization" for key in (headers or {})
        ):
            headers = {**(headers or {}), "Authorization": Omit()}
        messages = [{"role": "user", "content": message}]
        options = {"model": model, "timeout": REQUEST_TIMEOUT, "extra_headers": headers}
        if isinstance(raw, OpenAI) and endpoint.response_api:
            response = raw.responses.create(input=messages, max_output_tokens=2048, stream=False, **options)
            return {"content": response.output_text}
        if isinstance(raw, OpenAI):
            token_limit = "max_completion_tokens" if model.startswith(("gpt-5", "gpt-6", "o1", "o3", "o4")) else "max_tokens"
            response = raw.chat.completions.create(messages=messages, stream=False, **{token_limit: 2048}, **options)
            if not response.choices:
                raise RuntimeError("The endpoint returned no completion.")
            result = response.choices[0].message
            data = {"content": result.content or ""}
            reasoning = getattr(result, "reasoning_content", None)
            if isinstance(reasoning, str) and reasoning:
                data["reasoning_content"] = reasoning
            return data
        response = raw.messages.create(messages=messages, max_tokens=2048, stream=False, **options)
        data = {"content": "".join(block.text for block in response.content if block.type == "text")}
        reasoning = "".join(block.thinking for block in response.content if block.type == "thinking")
        if reasoning:
            data["reasoning_content"] = reasoning
        return data
