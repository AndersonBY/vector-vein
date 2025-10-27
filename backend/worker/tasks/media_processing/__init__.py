from worker.tasks import task, timer

from .gpt_vision import GPTVisionTask
from .glm_vision import GLMVisionTask
from .local_vision import LocalVisionTask
from .claude_vision import ClaudeVisionTask
from .gemini_vision import GeminiVisionTask
from .qwen_vision import QwenVisionTask
from .speech_recognition import speech_recognition


@task
@timer
def gpt_vision(
    workflow_data: dict,
    node_id: str,
):
    return GPTVisionTask(workflow_data, node_id).run()


@task
@timer
def glm_vision(
    workflow_data: dict,
    node_id: str,
):
    return GLMVisionTask(workflow_data, node_id).run()


@task
@timer
def local_vision(
    workflow_data: dict,
    node_id: str,
):
    return LocalVisionTask(workflow_data, node_id).run()


@task
@timer
def claude_vision(
    workflow_data: dict,
    node_id: str,
):
    return ClaudeVisionTask(workflow_data, node_id).run()


@task
@timer
def gemini_vision(
    workflow_data: dict,
    node_id: str,
):
    return GeminiVisionTask(workflow_data, node_id).run()


@task
@timer
def qwen_vision(
    workflow_data: dict,
    node_id: str,
):
    return QwenVisionTask(workflow_data, node_id).run()


__all__ = [
    "gpt_vision",
    "glm_vision",
    "local_vision",
    "claude_vision",
    "gemini_vision",
    "qwen_vision",
    "speech_recognition",
]
