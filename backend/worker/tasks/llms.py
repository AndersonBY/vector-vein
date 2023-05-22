# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-26 21:10:52
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-22 22:59:58
from typing import Union

import openai

from utilities.workflow import Workflow
from utilities.print_utils import mprint_error
from utilities.web_crawler import proxies_for_requests
from worker.tasks import task


@task
def open_ai(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    input_prompt: Union[str, list] = workflow.get_node_field_value(node_id, "prompt")
    temperature: float = workflow.get_node_field_value(node_id, "temperature")
    if workflow.setting.get("openai_api_type") == "azure":
        openai.api_type = "azure"
        openai.api_base = workflow.setting.get("openai_api_base")
        openai.api_version = "2023-03-15-preview"
        engine = workflow.setting.get("openai_chat_engine")
    else:
        openai.api_type = "open_ai"
        openai.api_base = "https://api.openai.com/v1"
        openai.api_version = None
        engine = None
    openai.api_key = workflow.setting.get("openai_api_key")
    openai.proxy = proxies_for_requests

    if isinstance(input_prompt, str):
        prompts = [input_prompt]
    elif isinstance(input_prompt, list):
        prompts = input_prompt

    results = []
    for prompt in prompts:
        messages = [
            {
                "role": "system",
                "content": prompt,
            },
        ]
        response = openai.ChatCompletion.create(
            engine=engine,
            messages=messages,
            temperature=temperature,
            max_tokens=2048,
            top_p=0.77,
        )
        result = response.choices[0].message.content
        results.append(result)

    output = results[0] if isinstance(input_prompt, str) else results
    workflow.update_node_field_value(node_id, "output", output)
    workflow.set_node_status(node_id, 200)
    return workflow.data
