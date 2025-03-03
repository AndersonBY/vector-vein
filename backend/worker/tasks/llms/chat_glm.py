# @Author: Bi Ying
# @Date:   2024-03-29 01:35:54
from vectorvein.types import BackendType
from .base_llm import BaseLLMTask


class ChatGLMTask(BaseLLMTask):
    MODEL_TYPE: BackendType = BackendType.ZhiPuAI
