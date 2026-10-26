# @Author: Bi Ying
# @Date:   2024-03-29 01:33:37
from vv_llm.types import BackendType
from .base_llm import BaseLLMTask


class ClaudeTask(BaseLLMTask):
    MODEL_TYPE: BackendType = BackendType.Anthropic
