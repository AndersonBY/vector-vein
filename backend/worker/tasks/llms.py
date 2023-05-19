# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-26 21:10:52
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-17 04:50:00
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
    prompt: str = workflow.get_node_field_value(node_id, "prompt")
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

    messages = [
        {
            "role": "system",
            "content": prompt,
        },
    ]
    try:
        response = openai.ChatCompletion.create(
            engine=engine,
            messages=messages,
            temperature=temperature,
            max_tokens=2048,
            top_p=0.77,
        )
        result = response.choices[0].message.content
        workflow.update_node_field_value(node_id, "output", result)
        workflow.set_node_status(node_id, 200)
        return workflow.data
    except Exception as e:
        mprint_error(e)
        workflow.set_node_status(node_id, 500)
