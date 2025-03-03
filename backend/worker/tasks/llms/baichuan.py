# @Author: Bi Ying
# @Date:   2024-03-29 01:32:25
from vectorvein.types import BackendType
from .base_llm import BaseLLMTask


class BaiChuanTask(BaseLLMTask):
    MODEL_TYPE: BackendType = BackendType.Baichuan
