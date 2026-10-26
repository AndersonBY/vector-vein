from vv_llm.types.enums import BackendType

from .base_vlm import BaseVLMTask


class GeminiVisionTask(BaseVLMTask):
    MODEL_TYPE: BackendType = BackendType.Gemini
    DEFAULT_MODEL = "gemini-3.5-flash"
    BASE64_ENCODE_IMAGE = True
