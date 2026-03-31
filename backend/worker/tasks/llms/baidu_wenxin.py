from vv_llm.types import BackendType

from .base_llm import BaseLLMTask


class WenXinTask(BaseLLMTask):
    MODEL_TYPE: BackendType = BackendType.Ernie
    MODEL_MAPPING: dict[str, str] = {
        "ernie-3.5": "ernie-3.5-128k",
        "ernie-4.0": "ernie-4.0-8k",
        "ernie-4.5": "ernie-4.5-8k-preview",
    }
