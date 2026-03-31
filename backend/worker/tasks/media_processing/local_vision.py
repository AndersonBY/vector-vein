from vv_llm.types.enums import BackendType

from .base_vlm import BaseVLMTask


class LocalVisionTask(BaseVLMTask):
    MODEL_TYPE: BackendType = BackendType.Local
