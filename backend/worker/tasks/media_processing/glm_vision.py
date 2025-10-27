from vectorvein.types.enums import BackendType

from .base_vlm import BaseVLMTask


class GLMVisionTask(BaseVLMTask):
    MODEL_TYPE: BackendType = BackendType.ZhiPuAI
    DEFAULT_MODEL = "glm-4.5b"
