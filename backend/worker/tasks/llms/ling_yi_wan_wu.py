# @Author: Bi Ying
# @Date:   2024-03-29 01:37:01
from vectorvein.types.enums import BackendType
from .base_llm import BaseLLMTask


class LingYiWanWuTask(BaseLLMTask):
    MODEL_TYPE: BackendType = BackendType.Yi
