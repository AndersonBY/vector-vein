from vv_llm.types import BackendType

from .base_llm import BaseLLMTask


class StepFunTask(BaseLLMTask):
    MODEL_TYPE: BackendType = BackendType.StepFun
