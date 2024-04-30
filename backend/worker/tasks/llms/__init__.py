# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-26 21:10:52
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-05-01 02:45:55
from worker.tasks import task, timer
from utilities.settings import Settings
from .open_ai import OpenAITask, AzureOpenAITask
from .moonshot import MoonshotTask
from .chat_glm import ChatGLMTask
from .claude import ClaudeTask


@task
@timer
def open_ai(
    workflow_data: dict,
    node_id: str,
):
    settings = Settings()
    if settings.openai_api_type == "azure":
        return AzureOpenAITask(workflow_data, node_id).run()
    else:
        return OpenAITask(workflow_data, node_id).run()


@task
@timer
def chat_glm(
    workflow_data: dict,
    node_id: str,
):
    return ChatGLMTask(workflow_data, node_id).run()


@task
@timer
def moonshot(
    workflow_data: dict,
    node_id: str,
):
    return MoonshotTask(workflow_data, node_id).run()


@task
@timer
def claude(
    workflow_data: dict,
    node_id: str,
):
    return ClaudeTask(workflow_data, node_id).run()
