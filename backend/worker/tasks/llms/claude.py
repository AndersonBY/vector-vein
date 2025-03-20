# @Author: Bi Ying
# @Date:   2024-03-29 01:33:37
from vectorvein.types import BackendType
from .base_llm import BaseLLMTask


class ClaudeTask(BaseLLMTask):
    MODEL_TYPE: BackendType = BackendType.Anthropic
    MODEL_MAPPING: dict[str, str] = {
        "claude-3-haiku": "claude-3-haiku-20240307",
        "claude-3-5-haiku": "claude-3-5-haiku-20241022",
        "claude-3-sonnet": "claude-3-sonnet-20240229",
        "claude-3-5-sonnet": "claude-3-5-sonnet-20241022",
        "claude-3-7-sonnet": "claude-3-7-sonnet-20250219",
        "claude-3-opus": "claude-3-opus-20240229",
    }
