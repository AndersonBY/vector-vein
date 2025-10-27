from vectorvein.types.enums import BackendType

from .base_vlm import BaseVLMTask


class GPTVisionTask(BaseVLMTask):
    MODEL_TYPE: BackendType = BackendType.OpenAI
    DEFAULT_MODEL = "gpt-4o"
