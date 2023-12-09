# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-26 21:10:52
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-12-09 17:28:58
import json
from typing import Union

import httpx
from openai import AzureOpenAI, OpenAI
from openai.types.chat import ChatCompletionMessage

from utilities.workflow import Workflow
from utilities.web_crawler import proxies
from worker.tasks import task


@task
def open_ai(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    input_prompt: Union[str, list] = workflow.get_node_field_value(node_id, "prompt")
    temperature: float = workflow.get_node_field_value(node_id, "temperature")
    response_format = workflow.get_node_field_value(node_id, "response_format", "text")
    use_function_call: bool = workflow.get_node_field_value(node_id, "use_function_call", False)
    functions: list = workflow.get_node_field_value(node_id, "functions", [])
    function_call_mode: str = workflow.get_node_field_value(node_id, "function_call_mode", "auto")

    if use_function_call:
        if function_call_mode not in ("auto", "none"):
            function_call_mode = {"type": "function", "function": {"name": function_call_mode}}
        function_call_parameters = {
            "tools": [{"type": "function", "function": function} for function in functions],
            "tool_choice": function_call_mode,
        }
    else:
        function_call_parameters = {}

    if response_format == "text":
        response_format_parameters = {}
    else:
        response_format_parameters = {"response_format": {"type": response_format}}

    openai_api_type = workflow.setting.get("openai_api_type")
    if openai_api_type == "azure":
        client = AzureOpenAI(
            azure_endpoint=workflow.setting.get("openai_api_base"),
            api_key=workflow.setting.get("openai_api_key"),
            api_version="2023-12-01-preview",
            http_client=httpx.Client(
                proxies=proxies(),
                transport=httpx.HTTPTransport(local_address="0.0.0.0"),
            ),
        )
        model = workflow.setting.get("openai_chat_engine")
    else:
        client = OpenAI(
            api_key=workflow.setting.get("openai_api_key"),
            base_url=workflow.setting.get("openai_api_base", "https://api.openai.com/v1"),
            http_client=httpx.Client(
                proxies=proxies(),
                transport=httpx.HTTPTransport(local_address="0.0.0.0"),
            ),
        )
        model = workflow.get_node_field_value(node_id, "llm_model")

    if isinstance(input_prompt, str):
        prompts = [input_prompt]
    elif isinstance(input_prompt, list):
        prompts = input_prompt

    content_outputs = []
    function_call_outputs = []
    function_call_arguments_batches = []
    for prompt in prompts:
        messages = [
            {
                "role": "system",
                "content": prompt,
            },
        ]
        response = client.chat.completions.create(
            model=model,
            **function_call_parameters,
            messages=messages,
            temperature=temperature,
            **response_format_parameters,
        )
        message: ChatCompletionMessage = response.choices[0].message
        content_output = message.content
        content_outputs.append(content_output)
        function_call_arguments = {}
        function_call_output = {}
        if message.tool_calls:
            for tool_call in message.tool_calls:
                try:
                    function_call_arguments = json.loads(tool_call.function.arguments)
                    function_call_output = tool_call.function.json()
                except json.decoder.JSONDecodeError:
                    print(tool_call.function)
                    function_call_arguments = {}
                    function_call_output = {}
                break
        function_call_outputs.append(function_call_output)
        function_call_arguments_batches.append(function_call_arguments)

    content_output = content_outputs[0] if isinstance(input_prompt, str) else content_outputs
    workflow.update_node_field_value(node_id, "output", content_output)
    function_call_output = function_call_outputs[0] if isinstance(input_prompt, str) else function_call_outputs
    workflow.update_node_field_value(node_id, "function_call_output", function_call_output)
    function_call_arguments_batches = (
        function_call_arguments_batches[0] if isinstance(input_prompt, str) else function_call_arguments_batches
    )
    workflow.update_node_field_value(node_id, "function_call_arguments", function_call_arguments_batches)
    workflow.set_node_status(node_id, 200)
    return workflow.data


@task
def chat_glm(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    input_prompt: Union[str, list] = workflow.get_node_field_value(node_id, "prompt")
    temperature: float = workflow.get_node_field_value(node_id, "temperature")
    model = workflow.get_node_field_value(node_id, "llm_model")
    if model == "chatglm-6b":
        api_base = workflow.setting.get("chatglm6b_api_base")
    else:
        raise ValueError("model not supported")

    if isinstance(input_prompt, str):
        prompts = [input_prompt]
    elif isinstance(input_prompt, list):
        prompts = input_prompt

    results = []
    for prompt in prompts:
        messages = {"prompt": prompt, "history": [], "temperature": temperature}
        response = httpx.post(api_base, json=messages, proxies=proxies(), timeout=None)
        result = response.json()["response"]
        results.append(result)

    output = results[0] if isinstance(input_prompt, str) else results
    workflow.update_node_field_value(node_id, "output", output)
    workflow.set_node_status(node_id, 200)
    return workflow.data
