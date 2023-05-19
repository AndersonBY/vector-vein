# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-16 18:15:11
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-16 20:04:54
import openai


def get_embedding_from_open_ai(text: str, setting: dict = None):
    openai.api_key = setting.get("openai_api_key")
    if setting.get("openai_api_type") == "azure":
        openai.api_type = "azure"
        openai.api_base = setting.get("openai_api_base")
        openai.api_version = "2022-12-01"
        engine = setting.get("openai_embedding_engine")
        return openai.Embedding.create(input=[text], engine=engine)["data"][0]["embedding"]
    else:
        openai.api_type = "open_ai"
        openai.api_base = "https://api.openai.com/v1"
        openai.api_version = None
        model = "text-embedding-ada-002"
        return openai.Embedding.create(input=[text], model=model)["data"][0]["embedding"]
