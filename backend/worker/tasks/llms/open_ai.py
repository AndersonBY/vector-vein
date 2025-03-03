# @Author: Bi Ying
# @Date:   2024-03-29 01:07:26
from vectorvein.types import BackendType
from .base_llm import BaseLLMTask


class OpenAITask(BaseLLMTask):
    MODEL_TYPE: BackendType = BackendType.OpenAI
