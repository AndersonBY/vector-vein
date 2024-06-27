# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-06-08 13:12:38
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-25 22:05:23
import time

import httpx

from utilities.config import Settings
from utilities.workflow import Workflow
from utilities.general import mprint, Retry
from utilities.ai_utils import create_chat_client
from utilities.media_processing import ImageProcessor, SpeechRecognitionClient
from worker.tasks import task, timer


@task
@timer
def gpt_vision(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    images_or_urls = workflow.get_node_field_value(node_id, "images_or_urls")
    detail_type = workflow.get_node_field_value(node_id, "detail_type", "auto")
    images = []
    if images_or_urls == "images":
        images = workflow.get_node_field_value(node_id, "images")
        if isinstance(images, str):
            images = [images]
    elif images_or_urls == "urls":
        urls = workflow.get_node_field_value(node_id, "urls")
        if isinstance(urls, str):
            images = [urls]

    text_prompt = workflow.get_node_field_value(node_id, "text_prompt")
    if isinstance(text_prompt, str):
        prompts = [text_prompt]
    elif isinstance(text_prompt, list):
        prompts = text_prompt

    if len(prompts) < len(images) and len(prompts) == 1:
        prompts = prompts * len(images)
    elif len(prompts) > len(images) and len(images) == 1:
        images = images * len(prompts)

    content_outputs = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    prompts_count = len(prompts)
    mprint(f"Prompts count: {prompts_count}")

    model = workflow.get_node_field_value(node_id, "model")
    client = create_chat_client("openai", model=model, stream=False)

    for index, prompt in enumerate(prompts):
        mprint(f"Processing prompt {index + 1}/{prompts_count}")
        image_processor = ImageProcessor(image_source=images[index])
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_processor.data_url,
                            "detail_type": detail_type,
                        },
                    },
                ],
            }
        ]

        response = client.create_completion(messages=messages)
        content_output = response["content"]
        content_outputs.append(content_output)
        total_prompt_tokens += response["usage"]["prompt_tokens"]
        total_completion_tokens += response["usage"]["completion_tokens"]

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
    images = []
    if images_or_urls == "images":
        images = workflow.get_node_field_value(node_id, "images")
        if isinstance(images, str):
            images = [images]
    elif images_or_urls == "urls":
        urls = workflow.get_node_field_value(node_id, "urls")
        if isinstance(urls, str):
            images = [urls]

    text_prompt = workflow.get_node_field_value(node_id, "text_prompt")
    if isinstance(text_prompt, str):
        prompts = [text_prompt]
    elif isinstance(text_prompt, list):
        prompts = text_prompt

    if len(prompts) < len(images) and len(prompts) == 1:
        prompts = prompts * len(images)
    elif len(prompts) > len(images) and len(images) == 1:
        images = images * len(prompts)

    content_outputs = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    prompts_count = len(prompts)
    mprint(f"Prompts count: {prompts_count}")

    client = create_chat_client("zhipuai", model="glm-4v", stream=False)
    for index, prompt in enumerate(prompts):
        mprint(f"Processing prompt {index + 1}/{prompts_count}")
        image_processor = ImageProcessor(image_source=images[index])
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_processor.base64_image},
                    },
                ],
            }
        ]

        response = client.create_completion(messages=messages, max_tokens=1024)

        content_output = response["content"]
        content_outputs.append(content_output)
        total_prompt_tokens += response["usage"]["prompt_tokens"]
        total_completion_tokens += response["usage"]["completion_tokens"]

        if index < prompts_count - 1:
            time.sleep(1)

    content_output = content_outputs[0] if isinstance(text_prompt, str) else content_outputs
    workflow.update_node_field_value(node_id, "output", content_output)
    return workflow.data


@task
@timer
def claude_vision(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    images_or_urls = workflow.get_node_field_value(node_id, "images_or_urls")
    images = []
    if images_or_urls == "images":
        images = workflow.get_node_field_value(node_id, "images")
        if isinstance(images, str):
            images = [images]
    elif images_or_urls == "urls":
        urls = workflow.get_node_field_value(node_id, "urls")
        if isinstance(urls, str):
            images = [urls]

    text_prompt = workflow.get_node_field_value(node_id, "text_prompt")
    if isinstance(text_prompt, str):
        prompts = [text_prompt]
    elif isinstance(text_prompt, list):
        prompts = text_prompt

    if len(prompts) < len(images) and len(prompts) == 1:
        prompts = prompts * len(images)
    elif len(prompts) > len(images) and len(images) == 1:
        images = images * len(prompts)

    content_outputs = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    prompts_count = len(prompts)
    mprint(f"Prompts count: {prompts_count}")

    model = workflow.get_node_field_value(node_id, "llm_model")
    if model == "claude-3-opus":
        model = "claude-3-opus-20240229"
    elif model == "claude-3-sonnet":
        model = "claude-3-sonnet-20240229"
    elif model == "claude-3-haiku":
        model = "claude-3-haiku-20240307"
    elif model == "claude-3-5-sonnet":
        model = "claude-3-5-sonnet-20240620"
    else:
        raise Exception(f"Model {model} not supported")

    client = create_chat_client("anthropic", model=model, stream=False)
    for index, prompt in enumerate(prompts):
        mprint(f"Processing prompt {index + 1}/{prompts_count}")
        image_processor = ImageProcessor(image_source=images[index])
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_processor.mime_type,
                            "data": image_processor.base64_image,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        response = client.create_completion(messages=messages, max_tokens=1024)

        content_output = response["content"]
        content_outputs.append(content_output)
        total_prompt_tokens += response["usage"]["prompt_tokens"]
        total_completion_tokens += response["usage"]["completion_tokens"]

        if index < prompts_count - 1:
            time.sleep(1)

    content_output = content_outputs[0] if isinstance(text_prompt, str) else content_outputs
    workflow.update_node_field_value(node_id, "output", content_output)
    return workflow.data


@task
@timer
def gemini_vision(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    images_or_urls = workflow.get_node_field_value(node_id, "images_or_urls")
    images = []
    if images_or_urls == "images":
        images = workflow.get_node_field_value(node_id, "images")
        if isinstance(images, str):
            images = [images]
    elif images_or_urls == "urls":
        urls = workflow.get_node_field_value(node_id, "urls")
        if isinstance(urls, str):
            images = [urls]

    text_prompt = workflow.get_node_field_value(node_id, "text_prompt")
    if isinstance(text_prompt, str):
        prompts = [text_prompt]
    elif isinstance(text_prompt, list):
        prompts = text_prompt

    if len(prompts) < len(images) and len(prompts) == 1:
        prompts = prompts * len(images)
    elif len(prompts) > len(images) and len(images) == 1:
        images = images * len(prompts)

    model = workflow.get_node_field_value(node_id, "llm_model")

    content_outputs = []
    total_tokens = 0
    prompts_count = len(prompts)
    mprint(f"Prompts count: {prompts_count}")

    settings = Settings()
    url = f"{settings.gemini_api_base}/models/{model}:generateContent"
    headers = {"Content-Type": "application/json"}
    params = {"key": settings.gemini_api_key}
    for index, prompt in enumerate(prompts):
        mprint(f"Processing prompt {index + 1}/{prompts_count}")
        image_processor = ImageProcessor(image_source=images[index])
        request_body = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mimeType": image_processor.mime_type,
                                "data": image_processor.base64_image,
                            }
                        },
                    ]
                }
            ]
        }

        gemini_request_success, response = (
            Retry(httpx.post)
            .args(
                url=url,
                json=request_body,
                headers=headers,
                params=params,
                timeout=None,
            )
            .retry_times(5)
            .sleep_time(5)
            .run()
        )
        if not gemini_request_success:
            mprint.error(f"Gemini request failed: {response}")
            content_outputs.append("")
            continue

        response = response.json()
        if "candidates" not in response:
            mprint.error(response)
            raise Exception("Invalid response from Gemini")

        content_output = response["candidates"][0]["content"]["parts"][0]["text"]
        content_outputs.append(content_output)
        total_tokens += int(len(prompt + content_output) / 1.5) + 258
        mprint(f"Tokens :{total_tokens}")

        if index < prompts_count - 1:
            time.sleep(5)

    content_output = content_outputs[0] if isinstance(text_prompt, str) else content_outputs

    workflow.update_node_field_value(node_id, "output", content_output)
    return workflow.data


@task
@timer
def speech_recognition(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    files_or_urls = workflow.get_node_field_value(node_id, "files_or_urls")
    if files_or_urls == "files":
        files = workflow.get_node_field_value(node_id, "files")
        if isinstance(files, str):
            files = [files]
        files_data = [open(file, "rb") for file in files]
    elif files_or_urls == "urls":
        urls = workflow.get_node_field_value(node_id, "urls")
        if isinstance(urls, str):
            urls = [urls]
        elif isinstance(urls, list):
            urls = urls
        files_data = [httpx.get(url).content for url in urls]

    client = SpeechRecognitionClient(provider="openai")
    output_type = workflow.get_node_field_value(node_id, "output_type")
    outputs = client.batch_transcribe(files_data, output_type)

    if files_or_urls == "urls":
        if isinstance(workflow.get_node_field_value(node_id, "urls"), str):
            outputs = outputs[0]
    elif files_or_urls == "files":
        if len(outputs) == 1:
            outputs = outputs[0]

    workflow.update_node_field_value(node_id, "output", outputs)
    return workflow.data
