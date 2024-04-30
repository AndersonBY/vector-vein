# @Author: Bi Ying
# @Date:   2024-04-11 20:37:32
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from openai import AzureOpenAI, OpenAI
from openai.types.chat import ChatCompletionMessage

from utilities.workflow import Workflow
from utilities.web_crawler import proxies
from utilities.embeddings import get_token_counts
from utilities.print_utils import mprint, mprint_error
from .types.model import ModelSetting
from .types.output import ModelOutput


class BaseLLMTask:
    NAME: str = "BaseLLMTask"
    DEFAULT_MODEL = None
    MODEL_SETTINGS: dict[str, ModelSetting] = {}
    SINGLE_PROCESS_TIMEOUT = 180

    def __init__(self, workflow_data: dict, node_id: str):
        self.workflow = Workflow(workflow_data)
        self.node_id = node_id
        self.model = self.workflow.get_node_field_value(node_id, "llm_model", self.DEFAULT_MODEL)
        self.input_prompt: str | list = self.workflow.get_node_field_value(node_id, "prompt")
        self.temperature: float = self.workflow.get_node_field_value(node_id, "temperature")
        self.model = self.workflow.get_node_field_value(node_id, "llm_model")
        response_format = self.workflow.get_node_field_value(node_id, "response_format", "text")
        self.use_function_call: bool = self.workflow.get_node_field_value(node_id, "use_function_call", False)
        self.functions: list = self.workflow.get_node_field_value(node_id, "functions", [])
        self.function_call_mode: str = self.workflow.get_node_field_value(node_id, "function_call_mode", "auto")

        self.model_settings = self.MODEL_SETTINGS[self.model]
        self.model_settings.refresh()

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

        if self.model_settings.response_format_available:
            self.response_format = {"response_format": {"type": response_format}}
        else:
            self.response_format = {}

        self.prompts_count = len(self.prompts)
        self.content_outputs = [""] * self.prompts_count
        self.function_call_outputs = [{}] * self.prompts_count
        self.function_call_arguments_batches = [{}] * self.prompts_count
        self.total_credits = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        mprint(f"Prompts count: {self.prompts_count}")

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

        input_token_counts = get_token_counts(prompt, self.model_settings.id)
        if self.model_settings.max_output_tokens is None:
            max_tokens = self.model_settings.max_tokens - input_token_counts - 64
        else:
            max_tokens = self.model_settings.max_output_tokens

        request_success = False
        response = None
        start_time = time.time()
        while time.time() - start_time < self.SINGLE_PROCESS_TIMEOUT and not request_success:
            # Check if any endpoint is available
            has_available_endpoint = False
            for endpoint in self.model_settings.endpoints:
                if endpoint.model_available(self.model_settings.id):
                    has_available_endpoint = True
                    break
            if not has_available_endpoint:
                time.sleep(1)
                continue

            if endpoint.is_azure:
                client = AzureOpenAI(
                    azure_endpoint=endpoint.endpoint,
                    api_key=endpoint.api_key,
                    api_version="2024-03-01-preview",
                    http_client=httpx.Client(
                        proxies=proxies(),
                        transport=httpx.HTTPTransport(local_address="0.0.0.0"),
                    ),
                )
            else:
                client = OpenAI(
                    api_key=endpoint.api_key,
                    base_url=endpoint.endpoint,
                    http_client=httpx.Client(
                        proxies=proxies(),
                        transport=httpx.HTTPTransport(local_address="0.0.0.0"),
                    ),
                )

            response = client.chat.completions.create(
                model=self.model_settings.id,
                messages=messages,
                temperature=self.temperature,
                max_tokens=max_tokens,
                timeout=60 * 3,
                **self.response_format,
                **self.function_call_parameters,
            )
            request_success = True

        message: ChatCompletionMessage = response.choices[0].message
        content_output = message.content
        tool_calls = []
        function_call_arguments = {}
        if message.tool_calls:
            tool_calls = [tool_call.model_dump() for tool_call in message.tool_calls]
            for tool_call in message.tool_calls:
                try:
                    function_call_arguments = json.loads(tool_call.function.arguments)
                except json.decoder.JSONDecodeError:
                    mprint_error(tool_call.function.arguments)
                    function_call_arguments = {}
                break

        if response.usage is None:
            prompt_tokens = get_token_counts(
                json.dumps(messages) + json.dumps(function_call_arguments), self.model_settings.id
            )
            completion = content_output + json.dumps(function_call_arguments)
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
        with ThreadPoolExecutor(max_workers=self.model_settings.concurrent) as executor:
            future_to_index = {
                executor.submit(self.process_prompt, prompt, index): index for index, prompt in enumerate(self.prompts)
            }

            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result()
                    self.content_outputs[index] = result.content_output
                    self.function_call_outputs[index] = result.tool_calls
                    self.function_call_arguments_batches[index] = result.function_call_arguments
                    self.total_prompt_tokens += result.prompt_tokens
                    self.total_completion_tokens += result.completion_tokens
                except Exception as exc:
                    mprint_error(f"Generated an exception: {exc}")
                    mprint_error(f"Prompt: {self.prompts[index]}")

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
