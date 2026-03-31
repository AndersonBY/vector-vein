# @Author: Bi Ying
# @Date:   2024-03-29 01:37:01
from vv_llm.types import BackendType
from .base_llm import BaseLLMTask


class LingYiWanWuTask(BaseLLMTask):
    MODEL_TYPE: BackendType = BackendType.Yi
