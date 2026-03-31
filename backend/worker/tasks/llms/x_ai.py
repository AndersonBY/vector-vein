from vv_llm.types import BackendType

from .base_llm import BaseLLMTask


class XAITask(BaseLLMTask):
    MODEL_TYPE: BackendType = BackendType.XAI
