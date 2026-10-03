from vv_llm.types.enums import BackendType

from .base_vlm import BaseVLMTask


class ClaudeVisionTask(BaseVLMTask):
    MODEL_TYPE: BackendType = BackendType.Anthropic
    DEFAULT_MODEL = "claude-opus-4-8"
