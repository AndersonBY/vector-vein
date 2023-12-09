# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-16 18:15:11
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-12-09 17:48:02
import httpx
import tiktoken
from openai import AzureOpenAI, OpenAI

from utilities.web_crawler import proxies


chatgpt_encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")


def get_token_counts(text: str, model: str = "gpt-3.5-turbo") -> int:
    if model == "gpt-3.5-turbo":
        return len(chatgpt_encoding.encode(text))
    else:
        return len(chatgpt_encoding.encode(text))


def get_embedding_from_open_ai(text: str, setting: dict = None):
    if setting.get("openai_api_type") == "azure":
        client = AzureOpenAI(
            azure_endpoint=setting.get("openai_api_base"),
            api_key=setting.get("openai_api_key"),
            api_version="2023-12-01-preview",
            http_client=httpx.Client(
                proxies=proxies(),
                transport=httpx.HTTPTransport(local_address="0.0.0.0"),
            ),
        )
        model = setting.get("openai_embedding_engine")
    else:
        client = OpenAI(
            api_key=setting.get("openai_api_key"),
            base_url=setting.get("openai_api_base", "https://api.openai.com/v1"),
            http_client=httpx.Client(
                proxies=proxies(),
                transport=httpx.HTTPTransport(local_address="0.0.0.0"),
            ),
        )
        model = "text-embedding-ada-002"

    return client.embeddings.create(input=[text], model=model).data[0].embedding
