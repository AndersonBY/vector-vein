# @Author: Bi Ying
# @Date:   2024-04-11 20:37:32
import json
import hashlib
import time
import random
from collections.abc import Generator
from typing import Any, Iterable, Literal, Protocol, TypeGuard, cast, overload
from concurrent.futures import ThreadPoolExecutor, as_completed

from vv_llm.chat_clients import create_chat_client
from vv_llm.chat_clients.base_client import BaseChatClient
from vv_llm.chat_clients.utils import get_token_counts, format_messages
from vv_llm.settings import settings as vv_llm_settings
from vv_llm.types import (
    APIStatusError,
    BackendType,
    ChatCompletionDeltaMessage,
    ChatCompletionMessage,
    ModelSetting,
    EndpointSetting,
    EndpointOptionDict,
    NotGiven,
    NOT_GIVEN,
    ToolParam,
    ToolChoice,
    ResponseFormat,
    ThinkingConfigEnabledParam,
    ThinkingConfigParam,
)

from utilities.config import Settings, cache
from utilities.workflow.structured_output import make_validator, validate_output
from utilities.workflow import Workflow
from utilities.general import mprint_with_name
from utilities.network.llm_client import new_llm_http_client
from utilities.general.ratelimit import is_request_allowed, add_request_record

from .types.output import ModelOutput


mprint = mprint_with_name(name="LLM Tasks")

ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]


class _ChatCompletionCreator(Protocol):
    @overload
    def __call__(
        self,
        *,
        messages: list[Any],
        model: str | None = None,
        stream: Literal[True],
        temperature: float | None | NotGiven = NOT_GIVEN,
        max_tokens: int | None | NotGiven = None,
        tools: Iterable[ToolParam] | NotGiven = NOT_GIVEN,
        tool_choice: ToolChoice | NotGiven = NOT_GIVEN,
        response_format: ResponseFormat | NotGiven = NOT_GIVEN,
        top_p: float | NotGiven | None = NOT_GIVEN,
        skip_cutoff: bool = False,
        thinking: ThinkingConfigParam | None | NotGiven = NOT_GIVEN,
        reasoning_effort: ReasoningEffort | None | NotGiven = NOT_GIVEN,
        extra_body: object | None = None,
    ) -> Generator[ChatCompletionDeltaMessage, Any, None]: ...

    @overload
    def __call__(
        self,
        *,
        messages: list[Any],
        model: str | None = None,
        stream: Literal[False] = False,
        temperature: float | None | NotGiven = NOT_GIVEN,
        max_tokens: int | None | NotGiven = None,
        tools: Iterable[ToolParam] | NotGiven = NOT_GIVEN,
        tool_choice: ToolChoice | NotGiven = NOT_GIVEN,
        response_format: ResponseFormat | NotGiven = NOT_GIVEN,
        top_p: float | NotGiven | None = NOT_GIVEN,
        skip_cutoff: bool = False,
        thinking: ThinkingConfigParam | None | NotGiven = NOT_GIVEN,
        reasoning_effort: ReasoningEffort | None | NotGiven = NOT_GIVEN,
        extra_body: object | None = None,
    ) -> ChatCompletionMessage: ...


def _enabled_thinking_config(
    thinking: ThinkingConfigParam | None | NotGiven,
) -> ThinkingConfigEnabledParam | None:
    if _is_enabled_thinking_config(thinking):
        return thinking
    return None


def _is_enabled_thinking_config(value: object) -> TypeGuard[ThinkingConfigEnabledParam]:
    if not isinstance(value, dict):
        return False
    return cast(dict[str, object], value).get("type") == "enabled"


def get_endpoint_id(endpoint_option: EndpointOptionDict | str) -> str:
    if isinstance(endpoint_option, str):
        return endpoint_option
    elif isinstance(endpoint_option, dict):
        return endpoint_option["endpoint_id"]
    else:
        raise ValueError(f"Invalid endpoint option: {endpoint_option}")


def model_available(model: ModelSetting, endpoint: EndpointSetting, add_record: bool = True) -> bool:
    """
    Check if the model is available under the current rate limits.

    Args:
        model_id (str): The ID of the model to check.
        add_record (bool, optional): Whether to add a request record. Defaults to True.

    Returns:
        bool: True if the request is allowed, False otherwise.
    """
    product = f"{model.id}:{endpoint.id}:{endpoint.api_key}"
    cycle = 60  # seconds
    max_count = endpoint.rpm

    return is_request_allowed(product, cycle, max_count, add_record)


def add_model_request_record(model: ModelSetting, endpoint: EndpointSetting) -> bool:
    """
    Add a request record for the model.

    Args:
        model_id (str): The ID of the model.

    Returns:
        bool: True if the record is added successfully, False otherwise.
    """
    product = f"{model.id}:{endpoint.id}:{endpoint.api_key}"
    cycle = 60

    return add_request_record(product, cycle)


class BaseLLMTask:
    MODEL_TYPE: BackendType
    NAME: str = "BaseLLMTask"
    SINGLE_PROCESS_TIMEOUT = 180

    def __init__(self, workflow_data: dict, node_id: str):
        self.workflow = Workflow(workflow_data)
        self.node_id = node_id
        self.model: str = self.workflow.get_node_field_value(node_id, "llm_model")
        self.input_prompt: str | list = self.workflow.get_node_field_value(node_id, "prompt")
        self.temperature: float | NotGiven = self.workflow.get_node_field_value(node_id, "temperature")
        response_format = self.workflow.get_node_field_value(node_id, "response_format", "text")
        self.use_function_call: bool = self.workflow.get_node_field_value(node_id, "use_function_call", False)
        self.functions: list = self.workflow.get_node_field_value(node_id, "functions", [])
        self.function_call_mode: str = self.workflow.get_node_field_value(node_id, "function_call_mode", "auto")
        self.stream: bool = self.workflow.get_node_field_value(node_id, "stream", False)
        self.top_p: float | NotGiven = self.workflow.get_node_field_value(node_id, "top_p", NOT_GIVEN)
        self.system_prompt: str = self.workflow.get_node_field_value(node_id, "system_prompt", "")
        self.output_validator = make_validator(self.workflow.get_node_field_value(node_id, "output_schema", ""))
        self.max_repairs = int(self.workflow.get_node_field_value(node_id, "max_repairs", 1))
        if not 0 <= self.max_repairs <= 2:
            raise ValueError("max_repairs must be between 0 and 2")
        self.cache_results = self.workflow.get_node_field_value(node_id, "cache_results", False) is True
        self.cache_version = self.workflow.get_node_field_value(node_id, "cache_version", "")
        if self.output_validator is not None and self.use_function_call:
            raise ValueError("Output schema validation and function calling must be used in separate nodes")

        user_settings = Settings()
        vv_llm_settings.load(user_settings.llm_settings)
        if not self.model:
            self.model = user_settings.llm_settings["backends"][self.MODEL_TYPE.value]["default_model"]

        self.thinking: ThinkingConfigParam | None | NotGiven = NOT_GIVEN
        self.reasoning_effort: ReasoningEffort | None | NotGiven = NOT_GIVEN
        self.extra_body: dict = {}
        if self.MODEL_TYPE == BackendType.OpenAI and self.model.startswith(("gpt-5", "gpt-6")):
            self.temperature = NOT_GIVEN
            self.top_p = NOT_GIVEN
        if self.MODEL_TYPE in (BackendType.Anthropic, BackendType.Qwen):
            self.stream = True
        if self.MODEL_TYPE == BackendType.Anthropic:
            self.temperature = NOT_GIVEN
            self.top_p = NOT_GIVEN

        self.chat_client = create_chat_client(
            backend=self.MODEL_TYPE,
            model=self.model,
            temperature=self.temperature,
            http_client=new_llm_http_client(is_async=False),
        )

        self.model_settings = self.chat_client.backend_settings.models[self.model]

        if isinstance(self.input_prompt, str):
            self.prompts = [self.input_prompt]
        elif isinstance(self.input_prompt, list):
            self.prompts = self.input_prompt

        self.tools: Iterable[ToolParam] | NotGiven = NOT_GIVEN
        self.tool_choice: ToolChoice | NotGiven = NOT_GIVEN
        if self.use_function_call and self.model_settings.function_call_available:
            if self.function_call_mode not in ("auto", "none"):
                self.tool_choice = {"type": "function", "function": {"name": self.function_call_mode}}
            else:
                if self.function_call_mode == "auto":
                    self.tool_choice = "auto"
                elif self.function_call_mode == "none":
                    self.tool_choice = "none"
                else:
                    self.tool_choice = "auto"
            self.tools = [{"type": "function", "function": function} for function in self.functions]

        self.response_format: ResponseFormat | NotGiven = NOT_GIVEN
        if response_format == "json_object" and self.model_settings.response_format_available:
            self.response_format = {"type": response_format}

        self.prompts_count = len(self.prompts)
        self.content_outputs = [""] * self.prompts_count
        self.reasoning_content_outputs = [""] * self.prompts_count
        self.function_call_outputs: list[list[dict[str, Any]]] = [list()] * self.prompts_count
        self.function_call_arguments_batches: list[dict[str, Any]] = [dict()] * self.prompts_count
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        mprint(f"Prompts count: {self.prompts_count}")

    def _create_stream_completion(
        self,
        chat_client: BaseChatClient,
        messages: list[Any],
        backend_type: BackendType,
        max_tokens: int,
    ) -> Generator[ChatCompletionDeltaMessage, Any, None]:
        create_completion = cast(_ChatCompletionCreator, chat_client.create_completion)
        return create_completion(
            model=self.model,
            messages=format_messages(messages, backend=backend_type),
            temperature=self.temperature,
            max_tokens=max_tokens,
            stream=True,
            response_format=self.response_format,
            tools=self.tools,
            tool_choice=self.tool_choice,
            top_p=self.top_p,
            skip_cutoff=True,
            thinking=self.thinking,
            reasoning_effort=self.reasoning_effort,
            extra_body=self.extra_body,
        )

    def _create_completion_response(
        self,
        chat_client: BaseChatClient,
        messages: list[Any],
        backend_type: BackendType,
        max_tokens: int,
    ) -> ChatCompletionMessage:
        create_completion = cast(_ChatCompletionCreator, chat_client.create_completion)
        return create_completion(
            model=self.model,
            messages=format_messages(messages, backend=backend_type),
            temperature=self.temperature,
            max_tokens=max_tokens,
            stream=False,
            response_format=self.response_format,
            tools=self.tools,
            tool_choice=self.tool_choice,
            top_p=self.top_p,
            skip_cutoff=True,
            thinking=self.thinking,
            reasoning_effort=self.reasoning_effort,
            extra_body=self.extra_body,
        )

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
        index: int,
    ) -> ModelOutput:
        mprint(f"Processing prompt {index + 1}/{self.prompts_count}")
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt})

        if self.model_settings.max_output_tokens is None:
            input_token_counts = get_token_counts(prompt, self.model, True)
            max_tokens = self.model_settings.context_length - input_token_counts - 64
        else:
            max_tokens = self.model_settings.max_output_tokens

        thinking_config = _enabled_thinking_config(self.thinking)
        if thinking_config is not None:
            max_tokens = 16000
            thinking_config["budget_tokens"] = max_tokens - 1000

        request_success = False
        stream_response: Generator[ChatCompletionDeltaMessage, Any, None] | None = None
        response: ChatCompletionMessage | None = None
        start_time = time.time()
        endpoints = self.model_settings.endpoints.copy()
        random.shuffle(endpoints)
        _chat_client: BaseChatClient = create_chat_client(
            backend=self.MODEL_TYPE,
            model=self.model,
            temperature=self.temperature,
        )
        while time.time() - start_time < self.SINGLE_PROCESS_TIMEOUT and not request_success:
            # 遍历所有端点，找到一个可用的
            for endpoint_option in endpoints:
                endpoint_id = get_endpoint_id(endpoint_option)
                endpoint = vv_llm_settings.get_endpoint(endpoint_id)
                if not self.endpoint_available(endpoint):
                    continue
                _chat_client.endpoint = endpoint
                if endpoint.endpoint_type and endpoint.endpoint_type.startswith("openai"):
                    backend_type = BackendType.OpenAI
                else:
                    backend_type = self.MODEL_TYPE
                try:
                    if self.stream:
                        stream_response = self._create_stream_completion(
                            _chat_client,
                            messages,
                            backend_type,
                            max_tokens,
                        )
                    else:
                        response = self._create_completion_response(
                            _chat_client,
                            messages,
                            backend_type,
                            max_tokens,
                        )
                    request_success = True
                    self.add_endpoint_request_record(endpoint)
                    break
                except APIStatusError as e:
                    if e.status_code == 429:
                        mprint.error(f"Rate limit exceeded with endpoint {endpoint.id}")
                        time.sleep(5)
                    else:
                        raise e
                except Exception as e:
                    mprint.error(f"Error with endpoint {endpoint.id}: {type(e).__name__}")

            if not request_success:
                time.sleep(1)

        if not request_success:
            raise Exception("Failed to request the model")

        tool_calls: list[dict[str, Any]] = []
        function_call_arguments: dict[str, Any] = {}
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
            if response.tool_calls:
                tool_calls = [tool_call.model_dump() for tool_call in response.tool_calls]
                for tool_call in response.tool_calls:
                    try:
                        function_call_arguments = json.loads(tool_call.function.arguments)
                    except json.decoder.JSONDecodeError:
                        mprint.error(tool_call.function.arguments)
                        function_call_arguments = {}
                    break

            if response.usage is None:
                prompt_tokens = get_token_counts(json.dumps(messages) + json.dumps(function_call_arguments), self.model, True)
                completion = content_output or "" + json.dumps(function_call_arguments)
                completion_tokens = get_token_counts(completion, self.model, True)
            else:
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens

        output = ModelOutput(
            content_output=content_output,
            reasoning_content=reasoning_content,
            tool_calls=tool_calls,
            function_call_arguments=function_call_arguments,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        return output

    def process_validated_prompt(self, prompt: str, index: int) -> ModelOutput:
        thinking = _enabled_thinking_config(self.thinking)
        if thinking is not None:
            self.thinking = cast(ThinkingConfigEnabledParam, {**thinking, "budget_tokens": 15000})
        validator = self.output_validator
        schema = validator.schema if validator is not None else None
        cache_key = None
        if self.cache_results:
            # Only the digest is persisted. Endpoint credentials and the key payload
            # stay in memory; changing endpoint/model configuration invalidates reuse.
            payload = {
                "version": 1, "namespace": self.cache_version, "task": type(self).__name__,
                "provider": self.MODEL_TYPE.value, "model": self.model_settings.model_dump(mode="json"),
                "endpoints": [vv_llm_settings.get_endpoint(get_endpoint_id(e)).model_dump(mode="json") for e in self.model_settings.endpoints],
                "prompt": prompt, "system_prompt": self.system_prompt, "schema": schema,
                "temperature": self.temperature, "top_p": self.top_p, "thinking": self.thinking,
                "reasoning_effort": self.reasoning_effort, "extra_body": self.extra_body,
                "response_format": self.response_format, "tools": self.tools, "tool_choice": self.tool_choice,
                "stream": self.stream,
            }
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=lambda value: "NOT_GIVEN" if isinstance(value, NotGiven) else str(value))
            cache_key = "llm-result:v1:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()
            saved = cache.get(cache_key)
            if saved is not None:
                result = ModelOutput.model_validate(saved)
                if validator is not None:
                    validate_output(result.content_output or "", validator)
                return result.model_copy(update={"cache_hit": True, "prompt_tokens": 0, "completion_tokens": 0})

        request_prompt = prompt
        if validator is not None:
            request_prompt += "\nReturn only JSON matching this schema:\n" + json.dumps(schema, ensure_ascii=False)
        prompt_tokens = completion_tokens = 0
        for attempt in range(self.max_repairs + 1):
            result = self.process_prompt(request_prompt, index)
            prompt_tokens += result.prompt_tokens
            completion_tokens += result.completion_tokens
            try:
                if validator is not None:
                    validate_output(result.content_output or "", validator)
                elif not result.content_output and not result.tool_calls:
                    raise ValueError("Model returned an empty response")
                break
            except ValueError as exc:
                if validator is None or attempt == self.max_repairs:
                    raise
                request_prompt = prompt + "\nReturn only corrected JSON matching this schema:\n" + json.dumps(schema, ensure_ascii=False)
                request_prompt += "\nValidation error: " + str(exc) + "\nPrevious output:\n" + (result.content_output or "")
        result = result.model_copy(update={"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens})
        if cache_key is not None:
            cache.set(cache_key, result.model_dump(mode="json"), expire=30 * 24 * 60 * 60)
        return result

    def run(self):
        failures = []
        cache_hits = 0
        max_concurrent = self.get_max_concurrent_requests()
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            future_to_index = {executor.submit(self.process_validated_prompt, prompt, index): index for index, prompt in enumerate(self.prompts)}

            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result()
                    self.content_outputs[index] = result.content_output or ""
                    self.reasoning_content_outputs[index] = result.reasoning_content or ""
                    self.function_call_outputs[index] = result.tool_calls or []
                    self.function_call_arguments_batches[index] = result.function_call_arguments or {}
                    cache_hits += int(result.cache_hit)
                    self.total_prompt_tokens += result.prompt_tokens
                    self.total_completion_tokens += result.completion_tokens
                except Exception as exc:
                    failures.append({"index": index, "error": type(exc).__name__})

        content_output = self.content_outputs[0] if isinstance(self.input_prompt, str) else self.content_outputs
        self.workflow.update_node_field_value(self.node_id, "output", content_output)

        reasoning_content = self.reasoning_content_outputs[0] if isinstance(self.input_prompt, str) else self.reasoning_content_outputs
        self.workflow.update_node_field_value(self.node_id, "reasoning_content", reasoning_content)

        if self.use_function_call and self.model_settings.function_call_available:
            function_call_output = self.function_call_outputs[0] if isinstance(self.input_prompt, str) else self.function_call_outputs
            self.workflow.update_node_field_value(self.node_id, "function_call_output", function_call_output)
            if isinstance(self.input_prompt, str):
                self.workflow.update_node_field_value(self.node_id, "function_call_arguments", self.function_call_arguments_batches[0])
            else:
                self.workflow.update_node_field_value(self.node_id, "function_call_arguments", self.function_call_arguments_batches)

        self.workflow.update_node_field_value(self.node_id, "run_stats", {
            "items": len(self.prompts), "cache_hits": cache_hits, "failures": sorted(failures, key=lambda item: item["index"]),
            "prompt_tokens": self.total_prompt_tokens, "completion_tokens": self.total_completion_tokens,
        })
        if failures:
            indexes = ", ".join(str(item["index"]) for item in sorted(failures, key=lambda item: item["index"]))
            raise RuntimeError(f"LLM batch failed at item indexes: {indexes}")
        return self.workflow.data

    def get_max_concurrent_requests(self):
        return max(vv_llm_settings.get_endpoint(get_endpoint_id(endpoint)).concurrent_requests for endpoint in self.model_settings.endpoints)
