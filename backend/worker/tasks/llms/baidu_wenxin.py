from vv_llm.types import BackendType

from .base_llm import BaseLLMTask


class WenXinTask(BaseLLMTask):
    MODEL_TYPE: BackendType = BackendType.Ernie
