# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-26 21:10:52
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-09-05 18:22:38
import json
from typing import Union

import httpx
import openai

from utilities.workflow import Workflow
from utilities.web_crawler import proxies, proxies_for_requests
from worker.tasks import task


@task
def open_ai(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    input_prompt: Union[str, list] = workflow.get_node_field_value(node_id, "prompt")
    temperature: float = workflow.get_node_field_value(node_id, "temperature")
    use_function_call: bool = workflow.get_node_field_value(node_id, "use_function_call", False)
    functions: list = workflow.get_node_field_value(node_id, "functions", [])
    function_call_mode: str = workflow.get_node_field_value(node_id, "function_call_mode", "auto")
    if use_function_call:
        if function_call_mode not in ("auto", "none"):
            function_call_mode = {"name": function_call_mode}
        function_call_parameters = {
            "functions": functions,
            "function_call": function_call_mode,
        }
    else:
        function_call_parameters = {}

    openai_api_type = workflow.setting.get("openai_api_type")
    if openai_api_type == "azure":
        openai.api_type = "azure"
        openai.api_base = workflow.setting.get("openai_api_base")
        openai.api_version = "2023-07-01-preview"
        engine_model_param = {"engine": workflow.setting.get("openai_chat_engine")}
    else:
        openai.api_type = "open_ai"
        openai.api_base = workflow.setting.get("openai_api_base", "https://api.openai.com/v1")
        openai.api_version = None
        model = workflow.get_node_field_value(node_id, "llm_model")
        engine_model_param = {"model": model}
    openai.api_key = workflow.setting.get("openai_api_key")
    openai.proxy = proxies_for_requests()

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
        response = openai.ChatCompletion.create(
            **engine_model_param,
            **function_call_parameters,
            messages=messages,
            temperature=temperature,
            top_p=0.77,
        )
        content_output = response.choices[0].message.get("content", "")
        content_outputs.append(content_output)
        function_call_output = response.choices[0].message.get("function_call", {})
        function_call_outputs.append(function_call_output)
        function_call_arguments = function_call_output.get("arguments", "")
        try:
            json.loads(function_call_arguments)
        except json.JSONDecodeError:
            function_call_arguments = {}
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
