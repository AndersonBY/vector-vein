# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-06-08 13:12:38
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-05-01 02:27:57
import time
import base64

import httpx
from openai import OpenAI, AzureOpenAI
from openai.types.chat import ChatCompletionMessage

from utilities.settings import Settings
from utilities.workflow import Workflow
from utilities.web_crawler import proxies
from utilities.print_utils import mprint
from worker.tasks import task, timer


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


@task
@timer
def gpt_vision(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    images_or_urls = workflow.get_node_field_value(node_id, "images_or_urls")
    if images_or_urls == "images":
        images = workflow.get_node_field_value(node_id, "images")
        image_urls = [f"data:image/jpeg;base64,{encode_image(file)}" for file in images]
    elif images_or_urls == "urls":
        urls = workflow.get_node_field_value(node_id, "urls")
        if isinstance(urls, str):
            urls = [urls]
        elif isinstance(urls, list):
            urls = urls
        image_urls = urls

    text_prompt = workflow.get_node_field_value(node_id, "text_prompt")
    if isinstance(text_prompt, str):
        prompts = [text_prompt]
    elif isinstance(text_prompt, list):
        prompts = text_prompt

    if len(prompts) < len(image_urls) and len(prompts) == 1:
        prompts = prompts * len(image_urls)
    elif len(prompts) > len(image_urls) and len(image_urls) == 1:
        image_urls = image_urls * len(prompts)

    content_outputs = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    prompts_count = len(prompts)
    mprint(f"Prompts count: {prompts_count}")

    settings = Settings()
    if settings.openai_api_type == "azure":
        client = AzureOpenAI(
            azure_endpoint=settings.azure_endpoint,
            api_key=settings.azure_api_key,
            api_version="2024-03-01-preview",
            http_client=httpx.Client(
                proxies=proxies(),
                transport=httpx.HTTPTransport(local_address="0.0.0.0"),
            ),
        )
        model_id = settings.azure_gpt_4v_deployment_id
    else:
        client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
            http_client=httpx.Client(
                proxies=proxies(),
                transport=httpx.HTTPTransport(local_address="0.0.0.0"),
            ),
        )
        model_id = "gpt-4-turbo"

    for index, prompt in enumerate(prompts):
        mprint(f"Processing prompt {index + 1}/{prompts_count}")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_urls[index]},
                    },
                ],
            }
        ]

        response = client.chat.completions.create(
            model=model_id,
            messages=messages,
            max_tokens=4096,
            timeout=60 * 3,
        )

        message: ChatCompletionMessage = response.choices[0].message
        content_output = message.content
        content_outputs.append(content_output)
        total_prompt_tokens += response.usage.prompt_tokens
        total_completion_tokens += response.usage.completion_tokens
        mprint(f"Tokens :{response.usage}")

        if index < prompts_count - 1:
            time.sleep(1)

    content_output = content_outputs[0] if isinstance(text_prompt, str) else content_outputs
    workflow.update_node_field_value(node_id, "output", content_output)
    return workflow.data


@task
@timer
def glm_vision(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    images_or_urls = workflow.get_node_field_value(node_id, "images_or_urls")
    if images_or_urls == "images":
        images = workflow.get_node_field_value(node_id, "images")
        image_urls = [f"{encode_image(file)}" for file in images]
    elif images_or_urls == "urls":
        urls = workflow.get_node_field_value(node_id, "urls")
        if isinstance(urls, str):
            urls = [urls]
        elif isinstance(urls, list):
            urls = urls
        image_urls = urls

    text_prompt = workflow.get_node_field_value(node_id, "text_prompt")
    if isinstance(text_prompt, str):
        prompts = [text_prompt]
    elif isinstance(text_prompt, list):
        prompts = text_prompt

    if len(prompts) < len(image_urls) and len(prompts) == 1:
        prompts = prompts * len(image_urls)
    elif len(prompts) > len(image_urls) and len(image_urls) == 1:
        image_urls = image_urls * len(prompts)

    content_outputs = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    prompts_count = len(prompts)
    mprint(f"Prompts count: {prompts_count}")

    settings = Settings()
    client = OpenAI(
        api_key=settings.zhipuai_api_key,
        base_url=settings.zhipuai_api_base,
        http_client=httpx.Client(
            proxies=proxies(),
            transport=httpx.HTTPTransport(local_address="0.0.0.0"),
        ),
    )

    for index, prompt in enumerate(prompts):
        mprint(f"Processing prompt {index + 1}/{prompts_count}")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_urls[index],
                        },
                    },
                ],
            }
        ]

        response = client.chat.completions.create(
            model="glm-4v",
            messages=messages,
        )

        message: ChatCompletionMessage = response.choices[0].message
        content_output = message.content
        content_outputs.append(content_output)
        total_prompt_tokens += response.usage.prompt_tokens
        total_completion_tokens += response.usage.completion_tokens
        mprint(f"Tokens :{response.usage}")

        if index < prompts_count - 1:
            time.sleep(1)

    content_output = content_outputs[0] if isinstance(text_prompt, str) else content_outputs
    workflow.update_node_field_value(node_id, "output", content_output)
    return workflow.data
