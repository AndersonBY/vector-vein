from vectorvein.types.enums import BackendType

from .base_vlm import BaseVLMTask


class QwenVisionTask(BaseVLMTask):
    DEFAULT_MODEL = "qwen-vl-plus"
    MODEL_TYPE: BackendType = BackendType.Qwen
