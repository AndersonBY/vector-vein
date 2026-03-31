from vv_llm.types import BackendType

from .base_llm import BaseLLMTask


class CustomModelTask(BaseLLMTask):
    MODEL_TYPE: BackendType = BackendType.Local
