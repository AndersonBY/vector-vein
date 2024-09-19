# @Author: Bi Ying
# @Date:   2024-03-29 01:26:27
from vectorvein.types.enums import BackendType
from .base_llm import BaseLLMTask


class MiniMaxTask(BaseLLMTask):
    MODEL_TYPE: str = BackendType.MiniMax
