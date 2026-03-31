from vv_llm.types import BackendType

from utilities.workflow import Workflow

from .base_llm import BaseLLMTask


class UniversalLLMTask(BaseLLMTask):
    PROVIDER_MAPPING = {
        "openai": BackendType.OpenAI,
        "anthropic": BackendType.Anthropic,
        "deepseek": BackendType.DeepSeek,
        "gemini": BackendType.Gemini,
        "groq": BackendType.Groq,
        "minimax": BackendType.MiniMax,
        "mistral": BackendType.Mistral,
        "moonshot": BackendType.Moonshot,
        "qwen": BackendType.Qwen,
        "yi": BackendType.Yi,
        "zhipuai": BackendType.ZhiPuAI,
        "baichuan": BackendType.Baichuan,
        "ernie": BackendType.Ernie,
        "stepfun": BackendType.StepFun,
        "xai": BackendType.XAI,
    }

    def __init__(self, workflow_data: dict, node_id: str):
        workflow = Workflow(workflow_data)
        provider = workflow.get_node_field_value(node_id, "model_provider", "") or "OpenAI"
        provider_key = str(provider).strip().lower()
        self.MODEL_TYPE = self.PROVIDER_MAPPING.get(provider_key, BackendType.OpenAI)
        super().__init__(workflow_data, node_id)
