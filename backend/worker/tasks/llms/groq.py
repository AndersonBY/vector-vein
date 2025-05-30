# @Author: Bi Ying
# @Date:   2024-03-29 01:38:17
from vectorvein.types import BackendType
from .base_llm import BaseLLMTask


class GroqTask(BaseLLMTask):
    MODEL_TYPE: BackendType = BackendType.Groq
