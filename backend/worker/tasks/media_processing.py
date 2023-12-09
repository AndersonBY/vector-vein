# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-06-08 13:12:38
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-12-09 17:06:05
import time
import base64

import httpx
from openai import OpenAI
from openai.types.chat import ChatCompletionMessage

from utilities.workflow import Workflow
from utilities.web_crawler import proxies
from utilities.print_utils import mprint
from worker.tasks import task


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


@task
def gpt_vision(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    images_or_urls = workflow.get_node_field_value(node_id, "images_or_urls")
    if images_or_urls == "images":
        images = workflow.get_node_field_value(node_id, "images")
        images_url = [f"data:image/jpeg;base64,{encode_image(file)}" for file in images]
    elif images_or_urls == "urls":
        urls = workflow.get_node_field_value(node_id, "urls")
        if isinstance(urls, str):
            urls = [urls]
        elif isinstance(urls, list):
            urls = urls
        images_url = urls

    text_prompt = workflow.get_node_field_value(node_id, "text_prompt")
    if isinstance(text_prompt, str):
        prompts = [text_prompt]
    elif isinstance(text_prompt, list):
        prompts = text_prompt

    if len(prompts) < len(images_url) and len(prompts) == 1:
        prompts = prompts * len(images_url)
    elif len(prompts) > len(images_url) and len(images_url) == 1:
        images_url = images_url * len(prompts)

    content_outputs = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    prompts_count = len(prompts)
    mprint(f"Prompts count: {prompts_count}")

    client = OpenAI(
        api_key=workflow.setting.get("openai_api_key"),
        base_url=workflow.setting.get("openai_api_base", "https://api.openai.com/v1"),
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
                        "image_url": {"url": images_url[index]},
                    },
                ],
            }
        ]

        response = client.chat.completions.create(
            model="gpt-4-vision-preview",
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

        # 如果当前不是最后一个prompt，那么需要等待一段时间，避免OpenAI的并发请求限制
        if index < prompts_count - 1:
            time.sleep(5)

    content_output = content_outputs[0] if isinstance(text_prompt, str) else content_outputs
    workflow.update_node_field_value(node_id, "output", content_output)
    return workflow.data
