# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-26 21:10:52
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-24 22:21:45
from worker.tasks import task, timer
from utilities.config import Settings
from .groq import GroqTask
from .gemini import GeminiTask
from .claude import ClaudeTask
from .aliyun_qwen import QwenTask
from .mini_max import MiniMaxTask
from .chat_glm import ChatGLMTask
from .baichuan import BaiChuanTask
from .moonshot import MoonshotTask
from .deepseek import DeepSeekTask
from .local_llm import LocalLLMTask
from .ling_yi_wan_wu import LineYiWanWuTask
from .open_ai import OpenAITask, AzureOpenAITask


@task
@timer
def groq(
    workflow_data: dict,
    node_id: str,
):
    return GroqTask(workflow_data, node_id).run()


@task
@timer
def aliyun_qwen(
    workflow_data: dict,
    node_id: str,
):
    return QwenTask(workflow_data, node_id).run()


@task
@timer
def baichuan(
    workflow_data: dict,
    node_id: str,
):
    return BaiChuanTask(workflow_data, node_id).run()


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


@task
@timer
def ling_yi_wan_wu(
    workflow_data: dict,
    node_id: str,
):
    return LineYiWanWuTask(workflow_data, node_id).run()


@task
@timer
def deepseek(
    workflow_data: dict,
    node_id: str,
):
    return DeepSeekTask(workflow_data, node_id).run()


@task
@timer
def gemini(
    workflow_data: dict,
    node_id: str,
):
    return GeminiTask(workflow_data, node_id).run()


@task
@timer
def mini_max(
    workflow_data: dict,
    node_id: str,
):
    return MiniMaxTask(workflow_data, node_id).run()


@task
@timer
def local_llm(
    workflow_data: dict,
    node_id: str,
):
    return LocalLLMTask(workflow_data, node_id).run()
