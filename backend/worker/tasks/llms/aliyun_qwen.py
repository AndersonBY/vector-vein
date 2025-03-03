# @Author: Bi Ying
# @Date:   2024-03-29 01:30:41
from vectorvein.types import BackendType
from .base_llm import BaseLLMTask


class QwenTask(BaseLLMTask):
    MODEL_TYPE: BackendType = BackendType.Qwen
