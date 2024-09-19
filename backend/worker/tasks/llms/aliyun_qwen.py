# @Author: Bi Ying
# @Date:   2024-03-29 01:30:41
from vectorvein.types.enums import BackendType
from .base_llm import BaseLLMTask


class QwenTask(BaseLLMTask):
    MODEL_TYPE: str = BackendType.Qwen
