from vv_llm.types.enums import BackendType

from .base_vlm import BaseVLMTask


class QwenVisionTask(BaseVLMTask):
    DEFAULT_MODEL = "qwen3.5-397b-a17b"
    MODEL_TYPE: BackendType = BackendType.Qwen
