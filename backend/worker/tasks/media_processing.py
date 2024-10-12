# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-06-08 13:12:38
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-07-10 17:57:12
import time

from vectorvein.types.enums import BackendType
from vectorvein.chat_clients import create_chat_client
from vectorvein.chat_clients.utils import format_messages
from vectorvein.settings import settings as vectorvein_settings

from worker.tasks import task, timer
from utilities.config import Settings
from utilities.workflow import Workflow
from utilities.general import mprint_with_name
from utilities.network import new_httpx_client
from utilities.media_processing import ImageProcessor, SpeechRecognitionClient


mprint = mprint_with_name(name="Media Processing Tasks")


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
    else:
        raise Exception("Invalid text_prompt")

    if len(prompts) < len(images) and len(prompts) == 1:
        prompts = prompts * len(images)
    elif len(prompts) > len(images) and len(images) == 1:
        images = images * len(prompts)

    content_outputs = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    prompts_count = len(prompts)
    mprint(f"Prompts count: {prompts_count}")

    user_settings = Settings()
    vectorvein_settings.load(user_settings.get("llm_settings"))
    model = workflow.get_node_field_value(node_id, "model")
    client = create_chat_client(backend=BackendType.OpenAI, model=model, stream=False)

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
        content_outputs.append(response.content)
        if response.usage:
            total_prompt_tokens += response.usage.prompt_tokens
            total_completion_tokens += response.usage.completion_tokens

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
    else:
        raise Exception("Invalid text_prompt")

    if len(prompts) < len(images) and len(prompts) == 1:
        prompts = prompts * len(images)
    elif len(prompts) > len(images) and len(images) == 1:
        images = images * len(prompts)

    content_outputs = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    prompts_count = len(prompts)
    mprint(f"Prompts count: {prompts_count}")

    user_settings = Settings()
    vectorvein_settings.load(user_settings.get("llm_settings"))
    model = workflow.get_node_field_value(node_id, "model", "glm-4v")
    client = create_chat_client(backend=BackendType.ZhiPuAI, model=model, stream=False)
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

        response = client.create_completion(messages=messages)
        content_outputs.append(response.content)
        if response.usage:
            total_prompt_tokens += response.usage.prompt_tokens
            total_completion_tokens += response.usage.completion_tokens

        if index < prompts_count - 1:
            time.sleep(1)

    content_output = content_outputs[0] if isinstance(text_prompt, str) else content_outputs
    workflow.update_node_field_value(node_id, "output", content_output)
    return workflow.data


@task
@timer
def local_vision(
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
    else:
        raise Exception("Invalid text_prompt")

    if len(prompts) < len(images) and len(prompts) == 1:
        prompts = prompts * len(images)
    elif len(prompts) > len(images) and len(images) == 1:
        images = images * len(prompts)

    model_id = workflow.get_node_field_value(node_id, "llm_model")

    content_outputs = []
    prompts_count = len(prompts)
    mprint(f"Prompts count: {prompts_count}")

    user_settings = Settings()
    vectorvein_settings.load(user_settings.get("llm_settings"))
    client = create_chat_client(backend=BackendType.Local, model=model_id, stream=False)
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
                        "image_url": {"url": image_processor.data_url},
                    },
                ],
            }
        ]

        response = client.create_completion(messages=messages)
        content_output = response.content
        content_outputs.append(content_output)

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
    else:
        raise Exception("Invalid text_prompt")

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
    if model.startswith("claude-3-opus"):
        model = "claude-3-opus-20240229"
    elif model.startswith("claude-3-sonnet"):
        model = "claude-3-sonnet-20240229"
    elif model.startswith("claude-3-haiku"):
        model = "claude-3-haiku-20240307"
    elif model.startswith("claude-3-5-sonnet"):
        model = "claude-3-5-sonnet-20240620"
    else:
        raise Exception(f"Model {model} not supported")

    user_settings = Settings()
    vectorvein_settings.load(user_settings.get("llm_settings"))
    client = create_chat_client(backend=BackendType.Anthropic, model=model, stream=False)
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

        response = client.create_completion(messages=messages)

        content_output = response.content
        content_outputs.append(content_output)
        if response.usage:
            total_prompt_tokens += response.usage.prompt_tokens
            total_completion_tokens += response.usage.completion_tokens

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
    else:
        raise Exception("Invalid text_prompt")

    if len(prompts) < len(images) and len(prompts) == 1:
        prompts = prompts * len(images)
    elif len(prompts) > len(images) and len(images) == 1:
        images = images * len(prompts)

    model = workflow.get_node_field_value(node_id, "llm_model")

    content_outputs = []
    total_tokens = 0
    prompts_count = len(prompts)
    mprint(f"Prompts count: {prompts_count}")

    user_settings = Settings()
    vectorvein_settings.load(user_settings.get("llm_settings"))
    client = create_chat_client(backend=BackendType.Gemini, model=model, stream=False)
    for index, prompt in enumerate(prompts):
        mprint(f"Processing prompt {index + 1}/{prompts_count}")
        vectorvein_messages = [
            {
                "author_type": "U",
                "content_type": "TXT",
                "content": {"text": prompt},
                "attachments": [images[index]],
            }
        ]
        messages = format_messages(vectorvein_messages, backend=BackendType.Gemini, native_multimodal=True)

        response = client.create_completion(messages=messages)
        content_output = response.content or ""
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
        http_client = new_httpx_client(is_async=False)
        files_data = [http_client.get(url).content for url in urls]
    else:
        raise Exception("Invalid files_or_urls")

    engine = workflow.get_node_field_value(node_id, "engine", "openai")
    client = SpeechRecognitionClient(provider=engine)
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
