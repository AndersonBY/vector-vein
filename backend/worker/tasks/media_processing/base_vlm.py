# @Author: Bi Ying
# @Date:   2024-04-11 20:37:32
import json
import time
import random
from typing import Any, cast
from traceback import format_exc
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai._types import NotGiven as OpenAINotGiven
from openai.types.chat import ChatCompletionMessageParam
from openai.types.chat.chat_completion_content_part_text_param import ChatCompletionContentPartTextParam
from openai.types.chat.chat_completion_content_part_image_param import ChatCompletionContentPartImageParam
from vectorvein.types.enums import BackendType
from vectorvein.types.exception import APIStatusError
from vectorvein.chat_clients import create_chat_client
from vectorvein.settings import settings as vectorvein_settings
from vectorvein.chat_clients.utils import get_token_counts, format_messages
from vectorvein.types import (
    EndpointSetting,
    EndpointOptionDict,
    NotGiven,
    NOT_GIVEN,
    ResponseFormat,
    ThinkingConfigEnabledParam,
    ChatCompletionDeltaMessage,
    ChatCompletionMessage,
)

from utilities.config import Settings
from utilities.workflow import Workflow
from utilities.text_processing import extract_url
from utilities.general import mprint_with_name, align_elements
from utilities.general.ratelimit import is_request_allowed, add_request_record
from ..llms.types.output import ModelOutput
from utilities.media_processing import ImageProcessor


mprint = mprint_with_name(name="Media Processing Tasks")


def get_endpoint_id(endpoint_option: EndpointOptionDict | str) -> str:
    if isinstance(endpoint_option, str):
        return endpoint_option
    elif isinstance(endpoint_option, dict):
        return endpoint_option["endpoint_id"]
    else:
        raise ValueError(f"Invalid endpoint option: {endpoint_option}")


class BaseVLMTask:
    MODEL_TYPE = BackendType.OpenAI
    DEFAULT_MODEL = "gpt-4o"
    SINGLE_PROCESS_TIMEOUT = 180
    BASE64_ENCODE_IMAGE = False
    MODEL_MAPPING: dict[str, str] = {}

    def __init__(self, workflow_data: dict, node_id: str):
        self.workflow = Workflow(workflow_data)
        self.node_id = node_id
        self.input_prompt: str | list = self.workflow.get_node_field_value(node_id, "text_prompt")
        self.model: str = self.workflow.get_node_field_value(node_id, "llm_model", self.DEFAULT_MODEL)
        self.stream: bool = self.workflow.get_node_field_value(node_id, "stream", False)
        self.detail_type = self.workflow.get_node_field_value(node_id, "detail_type", "auto")
        self.multiple_input = self.workflow.get_node_field_value(node_id, "multiple_input", False)
        response_format = self.workflow.get_node_field_value(node_id, "response_format", "text")
        images_or_urls = self.workflow.get_node_field_value(node_id, "images_or_urls")
        input_images: list[str] | list[list[str]] | None = self.workflow.get_node_field_value(node_id, "images")
        input_urls: list[str] | list[list[str]] | None = self.workflow.get_node_field_value(node_id, "urls")
        image_urls = []

        user_settings = Settings()
        vectorvein_settings.load(user_settings.llm_settings)

        if images_or_urls == "images":
            images = input_images
            if isinstance(images, str):
                images = [images]
            if isinstance(images, list) and len(images) > 0 and any(isinstance(img, list) for img in images):
                if not self.multiple_input:
                    raise Exception("list[list[str]] format is only supported when multiple_input=True")
                image_urls = []
                for img_batch in images:  # type: ignore[arg-type]
                    batch_urls = [
                        ImageProcessor(image_source=img_path, max_size=1024 * 1024 * 5).data_url
                        for img_path in cast(list[str], img_batch)
                    ]
                    image_urls.append(batch_urls)
            else:
                image_urls = [
                    ImageProcessor(image_source=img_path, max_size=1024 * 1024 * 5).data_url
                    for img_path in (images or [])
                ]
        elif images_or_urls == "urls":
            urls = input_urls
            if urls is None:
                raise ValueError("urls is None")
            if isinstance(urls, str):
                urls = [urls]
            if isinstance(urls, list) and len(urls) > 0 and any(isinstance(url, list) for url in urls):
                if not self.multiple_input:
                    raise Exception("list[list[str]] format is only supported when multiple_input=True")
                image_urls = []
                for url_batch in urls:  # type: ignore[arg-type]
                    extracted_urls = cast(list[str], extract_url(url_batch))
                    batch_urls = [
                        ImageProcessor(image_source=u, max_size=1024 * 1024 * 5).data_url
                        for u in extracted_urls
                    ]
                    image_urls.append(batch_urls)
            else:
                extracted_urls = cast(list[str], extract_url(urls))  # type: ignore[arg-type]
                image_urls = [
                    ImageProcessor(image_source=u, max_size=1024 * 1024 * 5).data_url
                    for u in extracted_urls
                ]
        else:
            raise Exception("Invalid images_or_urls")

        _image_urls: str | list[str] | list[list[str]] = image_urls
        if isinstance(image_urls, list) and len(image_urls) == 1 and not isinstance(image_urls[0], list):
            _image_urls = image_urls[0]

        if self.multiple_input and not (isinstance(_image_urls, list) and len(_image_urls) > 0 and isinstance(_image_urls[0], list)):
            _image_urls = [_image_urls]  # type: ignore

        self.has_list, (self.prompts, self.images) = align_elements((self.input_prompt, _image_urls))

        self.original_model = self.model

        if self.model.startswith(("o1", "o3-mini", "o4-mini", "gpt-5")):
            self.temperature = 1.0
            self.top_p = 1
            self.stream = False

        if self.model and self.model.startswith(("o3-mini", "o4-mini")):
            self.top_p = NOT_GIVEN

        if self.model in (
            "claude-3-7-sonnet-thinking",
            "claude-opus-4-20250514-thinking",
            "claude-opus-4-1-20250805-thinking",
            "claude-sonnet-4-20250514-thinking",
            "claude-sonnet-4-5-20250929-thinking",
        ):
            self.original_model = self.model = self.model.removesuffix("-thinking")
            self.thinking: ThinkingConfigEnabledParam | NotGiven = {"type": "enabled", "budget_tokens": 16000}
            self.temperature = 1.0
        else:
            self.thinking = NOT_GIVEN

        if self.model.startswith(("claude-opus-4", "claude-sonnet-4")):
            self.stream = True

        self.reasoning_effort: OpenAINotGiven | str = NOT_GIVEN
        if self.model == "o3-mini-high":
            self.original_model = self.model = "o3-mini"
            self.reasoning_effort = "high"

        if self.model == "o4-mini-high":
            self.original_model = self.model = "o4-mini"
            self.reasoning_effort = "high"

        self.extra_body: dict[str, bool | int | dict] = {}
        if self.model.startswith("qwen3"):
            self.stream = True  # 百炼上思考模式只支持流式输出
            if self.model.endswith("-thinking"):
                if self.model not in [
                    "qwen3-next-80b-a3b-thinking",
                    "qwen3-vl-235b-a22b-thinking",
                    "qwen3-vl-32b-thinking",
                    "qwen3-vl-30b-a3b-thinking",
                    "qwen3-vl-8b-thinking",
                ]:
                    self.model = self.model.removesuffix("-thinking")
                self.extra_body = {"enable_thinking": True}
            else:
                self.extra_body = {"enable_thinking": False}

        if self.model.startswith("glm-4.") and self.model.endswith("-thinking"):
            self.model = self.model.removesuffix("-thinking")
            self.extra_body = {
                "thinking": {
                    "type": "enabled",
                },
            }

        self.model = self.MODEL_MAPPING.get(self.model, self.model)
        self.model_settings = vectorvein_settings.get_backend(self.MODEL_TYPE).models[self.model]

        self.response_format: ResponseFormat | NotGiven = NOT_GIVEN
        if response_format == "json_object" and self.model_settings.response_format_available:
            self.response_format = {"type": response_format}

        self.prompts_count = len(self.prompts)
        self.content_outputs = [""] * self.prompts_count
        self.reasoning_content_outputs = [""] * self.prompts_count
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    def endpoint_available(self, endpoint: EndpointSetting, add_record: bool = True) -> bool:
        """
        Check if the endpoint is available under the current rate limits.

        Args:
            endpoint (EndpointSetting): The endpoint to check.
            add_record (bool, optional): Whether to add a request record. Defaults to True.

        Returns:
            bool: True if the request is allowed, False otherwise.
        """
        product = f"{self.model_settings.id}:{endpoint.id}:{endpoint.api_key}"
        cycle = 60  # seconds
        max_count = endpoint.rpm

        return is_request_allowed(product, cycle, max_count, add_record)

    def add_endpoint_request_record(self, endpoint: EndpointSetting) -> bool:
        """
        Add a request record for the endpoint.

        Args:
            endpoint (EndpointSetting): The endpoint to add a request record for.

        Returns:
            bool: True if the record is added successfully, False otherwise.
        """
        product = f"{self.model_settings.id}:{endpoint.id}:{endpoint.api_key}"
        cycle = 60

        return add_request_record(product, cycle)

    def process_prompt(
        self,
        prompt: str,
        image: str | list[str],
        index: int,
    ) -> ModelOutput:
        mprint(f"Processing prompt {index + 1}/{self.prompts_count}")

        content: list[ChatCompletionContentPartTextParam | ChatCompletionContentPartImageParam] = [{"type": "text", "text": prompt}]

        if self.multiple_input:
            if not isinstance(image, list):
                image = [image]
            for img_url in image:
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": img_url,
                            "detail": self.detail_type,
                        },
                    }
                )
        elif not isinstance(image, list):
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image,
                        "detail": self.detail_type,
                    },
                }
            )
        else:
            raise Exception("multiple_input is False but image is a list")

        messages: list[ChatCompletionMessageParam] = [
            {
                "role": "user",
                "content": content,
            }
        ]

        if self.model_settings.max_output_tokens is None:
            input_token_counts = get_token_counts(prompt, self.model, True)
            max_tokens = self.model_settings.context_length - input_token_counts - 64
        else:
            max_tokens = max(1, self.model_settings.max_output_tokens)

        if self.thinking:
            self.thinking["budget_tokens"] = max_tokens - 10

        request_success = False
        stream_response = response = None
        start_time = time.time()
        endpoints = self.model_settings.endpoints.copy()
        random.shuffle(endpoints)
        _chat_client = create_chat_client(
            backend=self.MODEL_TYPE,
            model=self.model,
        )  # 单独创建一个 chat_client 对象，避免赋值 endpoint 时产生冲突
        while time.time() - start_time < self.SINGLE_PROCESS_TIMEOUT and not request_success:
            # 遍历所有端点，找到一个可用的
            for endpoint_option in endpoints:
                endpoint_id = get_endpoint_id(endpoint_option)
                endpoint = vectorvein_settings.get_endpoint(endpoint_id)
                if not self.endpoint_available(endpoint):
                    continue
                if self.thinking and endpoint.endpoint_type and endpoint.endpoint_type.startswith("openai"):  # TODO: openrouter 不支持 claude-3-7-sonnet 的 thinking 参数
                    continue
                _chat_client.endpoint = endpoint
                try:
                    if self.stream:
                        stream_response = cast(
                            Generator[ChatCompletionDeltaMessage, Any, None],
                            _chat_client.create_completion(
                                model=self.model,
                                messages=format_messages(messages, backend=self.MODEL_TYPE, native_multimodal=True),
                                max_tokens=max_tokens,
                                stream=True,
                                response_format=self.response_format,
                                skip_cutoff=True,
                                thinking=self.thinking,
                                reasoning_effort=self.reasoning_effort,  # type: ignore
                            ),
                        )
                    else:
                        response = cast(
                            ChatCompletionMessage,
                            _chat_client.create_completion(
                                model=self.model,
                                messages=format_messages(messages, backend=self.MODEL_TYPE, native_multimodal=True),
                                max_tokens=max_tokens,
                                stream=False,
                                response_format=self.response_format,
                                skip_cutoff=True,
                                thinking=self.thinking,
                                reasoning_effort=self.reasoning_effort,  # type: ignore
                            ),
                        )
                    request_success = True
                    self.add_endpoint_request_record(endpoint)
                    break
                except APIStatusError as e:
                    if e.status_code == 429:
                        mprint.error(f"Rate limit exceeded with endpoint {endpoint.id}: {e}")
                        time.sleep(5)
                    else:
                        raise e
                except Exception as e:
                    mprint.error(f"Error with endpoint {endpoint.id}: {str(e)}")
                    mprint.error(format_exc())

            if not request_success:
                time.sleep(1)

        if not request_success:
            raise Exception("Failed to request the model")

        if self.stream:
            if stream_response is None:
                raise Exception("Failed to stream the model")

            self.workflow.set_node_status(self.node_id, 202)

            content_output = ""
            reasoning_content = ""
            prompt_tokens = 0
            completion_tokens = 0

            reported = False
            for chunk in stream_response:
                if not reported:
                    self.workflow.report_node_status(self.node_id)
                    reported = True

                if chunk.usage:
                    prompt_tokens = chunk.usage.prompt_tokens
                    completion_tokens = chunk.usage.completion_tokens

                chunk_content = chunk.content
                if chunk_content:
                    content_output += chunk_content
                    self.workflow.push_node_data(self.node_id, {"content": chunk_content})
                chunk_reasoning_content = chunk.reasoning_content
                if chunk_reasoning_content:
                    reasoning_content += chunk_reasoning_content
                    self.workflow.push_node_data(self.node_id, {"reasoning_content": chunk_reasoning_content})

            self.workflow.push_node_data(self.node_id, {"end": True})

            if prompt_tokens == completion_tokens == 0:
                prompt_tokens = get_token_counts(json.dumps(messages, ensure_ascii=False), self.model, True)
                completion_tokens = get_token_counts(content_output, self.model, True)
        else:
            if response is None:
                raise Exception("Failed to get the model response")

            content_output = response.content or ""
            reasoning_content = response.reasoning_content or ""

            if response.usage is None:
                prompt_tokens = get_token_counts(json.dumps(messages, ensure_ascii=False), self.model, True)
                completion = content_output or ""
                completion_tokens = get_token_counts(completion, self.model, True)
            else:
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens

        output = ModelOutput(
            content_output=content_output,
            reasoning_content=reasoning_content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        return output

    def run(self):
        max_concurrent = self.get_max_concurrent_requests()
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            future_to_index = {
                executor.submit(self.process_prompt, prompt, image, index): index for index, (prompt, image) in enumerate(zip(self.prompts, self.images, strict=False))
            }

            for future in as_completed(future_to_index):
                index = future_to_index[future]
                retry_count = 0
                max_retries = 3

                while retry_count < max_retries:
                    try:
                        result = future.result()
                        self.content_outputs[index] = result.content_output or ""
                        self.reasoning_content_outputs[index] = result.reasoning_content or ""
                        self.total_prompt_tokens += result.prompt_tokens
                        self.total_completion_tokens += result.completion_tokens
                        break
                    except Exception as exc:
                        retry_count += 1
                        mprint.error(f"Attempt {retry_count}/{max_retries} - Generated an exception: {exc}")
                        mprint.error(f"Prompt: {self.prompts[index]}")

                        if retry_count >= max_retries:
                            mprint.error(f"Failed after {max_retries} attempts for prompt index {index}")
                        else:
                            future = executor.submit(self.process_prompt, self.prompts[index], self.images[index], index)

            content_output = self.content_outputs[0] if not self.has_list or self.multiple_input else self.content_outputs
            self.workflow.update_node_field_value(self.node_id, "output", content_output)

            reasoning_content = self.reasoning_content_outputs[0] if not self.has_list and not self.multiple_input else self.reasoning_content_outputs
            self.workflow.update_node_field_value(self.node_id, "reasoning_content", reasoning_content)

            return self.workflow.data

    def get_max_concurrent_requests(self):
        return max(vectorvein_settings.get_endpoint(get_endpoint_id(endpoint)).concurrent_requests for endpoint in self.model_settings.endpoints)
