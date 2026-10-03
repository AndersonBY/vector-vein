"""HTTP clients for vv-llm and the OpenAI/Anthropic 3.x/1.x SDKs."""

from typing import Literal, overload

import httpx2

from utilities.config import Settings
from .web_crawler import proxies_for_requests


@overload
def new_llm_http_client(is_async: Literal[False] = False) -> httpx2.Client: ...


@overload
def new_llm_http_client(is_async: Literal[True]) -> httpx2.AsyncClient: ...


def new_llm_http_client(is_async: bool = False) -> httpx2.Client | httpx2.AsyncClient:
    settings = Settings()
    transport = httpx2.AsyncHTTPTransport if is_async else httpx2.HTTPTransport
    mounts = {f"{protocol}://": transport(proxy=proxy) for protocol, proxy in proxies_for_requests().items()}
    client = httpx2.AsyncClient if is_async else httpx2.Client
    return client(
        mounts=mounts,
        trust_env=False,
        verify=not settings.get("skip_ssl_verification", False),
    )
