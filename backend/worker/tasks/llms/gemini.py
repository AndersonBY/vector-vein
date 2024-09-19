# @Author: Bi Ying
# @Date:   2024-03-29 01:34:55
from vectorvein.types.enums import BackendType
from .base_llm import BaseLLMTask


class GeminiTask(BaseLLMTask):
    MODEL_TYPE: str = BackendType.Gemini
