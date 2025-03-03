# @Author: Bi Ying
# @Date:   2024-03-29 01:26:27
from vectorvein.types import BackendType
from .base_llm import BaseLLMTask


class MiniMaxTask(BaseLLMTask):
    MODEL_TYPE: BackendType = BackendType.MiniMax
