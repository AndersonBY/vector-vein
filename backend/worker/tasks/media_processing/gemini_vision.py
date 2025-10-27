from vectorvein.types.enums import BackendType

from .base_vlm import BaseVLMTask


class GeminiVisionTask(BaseVLMTask):
    MODEL_TYPE: BackendType = BackendType.Gemini
    DEFAULT_MODEL = "gemini-1.5-pro"
    BASE64_ENCODE_IMAGE = True
    MODEL_MAPPING: dict[str, str] = {
        "gemini-2.5-pro-exp-03-25": "gemini-2.5-pro",
        "gemini-1.5-flash": "gemini-2.5-flash",
        "gemini-1.5-pro": "gemini-2.5-pro",
        "gemini-2.5-pro-preview-03-25": "gemini-2.5-pro",
        "gemini-2.5-pro-preview-05-06": "gemini-2.5-pro",
        "gemini-2.5-pro-preview-06-05": "gemini-2.5-pro",
        "gemini-2.0-flash": "gemini-2.5-flash",
        "gemini-2.5-flash-preview-04-17": "gemini-2.5-flash",
        "gemini-2.5-flash-preview-05-20": "gemini-2.5-flash",
    }
