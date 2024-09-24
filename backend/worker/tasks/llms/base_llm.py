# @Author: Bi Ying
# @Date:   2024-04-11 20:37:32
import json
import time
from traceback import format_exc
from concurrent.futures import ThreadPoolExecutor, as_completed

from vectorvein.types.enums import BackendType
from vectorvein.types.exception import APIStatusError
from vectorvein.chat_clients import create_chat_client
from vectorvein.settings import settings as vectorvein_settings
from vectorvein.types.llm_parameters import EndpointSetting, ModelSetting
from vectorvein.chat_clients.utils import get_token_counts, format_messages

from utilities.general import mprint
from utilities.config import Settings
from utilities.workflow import Workflow
from utilities.network import new_httpx_client
from utilities.general.ratelimit import is_request_allowed, add_request_record

from .types.output import ModelOutput


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
        self.model = self.workflow.get_node_field_value(node_id, "llm_model")
        self.input_prompt: str | list = self.workflow.get_node_field_value(node_id, "prompt")
        self.temperature: float = self.workflow.get_node_field_value(node_id, "temperature")
        response_format = self.workflow.get_node_field_value(node_id, "response_format", "text")
        self.use_function_call: bool = self.workflow.get_node_field_value(node_id, "use_function_call", False)
        self.functions: list = self.workflow.get_node_field_value(node_id, "functions", [])
        self.function_call_mode: str | dict = self.workflow.get_node_field_value(node_id, "function_call_mode", "auto")

        user_settings = Settings()
        vectorvein_settings.load(user_settings.llm_settings)
        self.chat_client = create_chat_client(
            backend=self.MODEL_TYPE,
            model=self.model,
            temperature=self.temperature,
            http_client=new_httpx_client(is_async=False),
        )

        self.model_settings = self.chat_client.backend_settings.models[self.model]

        if isinstance(self.input_prompt, str):
            self.prompts = [self.input_prompt]
        elif isinstance(self.input_prompt, list):
            self.prompts = self.input_prompt

        if self.use_function_call and self.model_settings.function_call_available:
            if self.function_call_mode not in ("auto", "none"):
                self.function_call_mode = {"type": "function", "function": {"name": self.function_call_mode}}
            self.function_call_parameters = {
                "tools": [{"type": "function", "function": function} for function in self.functions],
                "tool_choice": self.function_call_mode,
            }
        else:
            self.function_call_parameters = {}

        if response_format == "json_object" and self.model_settings.response_format_available:
            self.response_format = {"response_format": {"type": response_format}}
        else:
            self.response_format = {}

        self.prompts_count = len(self.prompts)
        self.content_outputs = [""] * self.prompts_count
        self.function_call_outputs = [list()] * self.prompts_count
        self.function_call_arguments_batches = [dict()] * self.prompts_count
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        mprint(f"Prompts count: {self.prompts_count}")

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
        messages = [
            {
                "role": "user",
                "content": prompt,
            },
        ]

        input_token_counts = get_token_counts(prompt, self.model)
        if self.model_settings.max_output_tokens is None:
            max_tokens = self.model_settings.context_length - input_token_counts - 64
        else:
            max_tokens = self.model_settings.max_output_tokens
            max_tokens = min(max(max_tokens, 1), self.model_settings.max_output_tokens)

        request_success = False
        response = None
        start_time = time.time()
        while time.time() - start_time < self.SINGLE_PROCESS_TIMEOUT and not request_success:
            # 遍历所有端点，找到一个可用的
            for endpoint_id in self.model_settings.endpoints:
                endpoint = vectorvein_settings.get_endpoint(endpoint_id)
                if self.endpoint_available(endpoint):
                    self.chat_client.endpoint = endpoint
                    try:
                        response = self.chat_client.create_completion(
                            model=self.model,
                            messages=format_messages(messages, backend=self.MODEL_TYPE),
                            stream=False,
                            temperature=self.temperature,
                            max_tokens=max_tokens,
                            **self.response_format,
                            **self.function_call_parameters,
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

        if response is None:
            raise Exception("Failed to get the model response")

        content_output = response.content
        tool_calls = []
        function_call_arguments = {}
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
            prompt_tokens = get_token_counts(json.dumps(messages) + json.dumps(function_call_arguments), self.model)
            completion = content_output or "" + json.dumps(function_call_arguments)
            completion_tokens = get_token_counts(completion)
        else:
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens

        output = ModelOutput(
            content_output=content_output,
            tool_calls=tool_calls,
            function_call_arguments=function_call_arguments,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        return output

    def run(self):
        max_concurrent = self.get_max_concurrent_requests()
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            future_to_index = {
                executor.submit(self.process_prompt, prompt, index): index for index, prompt in enumerate(self.prompts)
            }

            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result()
                    self.content_outputs[index] = result.content_output or ""
                    self.function_call_outputs[index] = result.tool_calls or []
                    self.function_call_arguments_batches[index] = result.function_call_arguments or {}
                    self.total_prompt_tokens += result.prompt_tokens
                    self.total_completion_tokens += result.completion_tokens
                except Exception as exc:
                    mprint.error(f"Generated an exception: {exc}")
                    mprint.error(f"Prompt: {self.prompts[index]}")

        content_output = self.content_outputs[0] if isinstance(self.input_prompt, str) else self.content_outputs
        self.workflow.update_node_field_value(self.node_id, "output", content_output)

        if self.use_function_call and self.model_settings.function_call_available:
            function_call_output = (
                self.function_call_outputs[0] if isinstance(self.input_prompt, str) else self.function_call_outputs
            )
            self.workflow.update_node_field_value(self.node_id, "function_call_output", function_call_output)
            self.function_call_arguments_batches = (
                self.function_call_arguments_batches[0]
                if isinstance(self.input_prompt, str)
                else self.function_call_arguments_batches
            )
            self.workflow.update_node_field_value(
                self.node_id, "function_call_arguments", self.function_call_arguments_batches
            )

        return self.workflow.data

    def get_max_concurrent_requests(self):
        return max(
            vectorvein_settings.get_endpoint(endpoint).concurrent_requests
            for endpoint in self.model_settings.endpoints
        )
