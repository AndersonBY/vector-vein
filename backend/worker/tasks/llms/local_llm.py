# @Author: Bi Ying
# @Date:   2024-03-29 01:35:54
from utilities.settings import Settings
from utilities.workflow import Workflow
from .base_llm import BaseLLMTask
from .types.model import ModelSetting, EndpointSetting


class LocalLLMTask(BaseLLMTask):
    NAME: str = "LocalLLM"
    DEFAULT_MODEL: str = ""
    MODEL_SETTINGS: dict[str, ModelSetting] = {}

    def __init__(self, workflow_data: dict, node_id: str):
        workflow = Workflow(workflow_data)
        model_family = workflow.get_node_field_value(node_id, "model_family")
        model_id = workflow.get_node_field_value(node_id, "llm_model")
        settings = Settings()
        model_family_settings = next(
            (item for item in settings.local_llms if item["model_family"] == model_family), None
        )
        selected_model_settings = next(
            (item for item in model_family_settings["models"] if item["model_id"] == model_id), None
        )
        endpoint = EndpointSetting(
            endpoint=model_family_settings["api_base"],
            api_key=model_family_settings["api_key"],
            rpm=selected_model_settings.get("rpm", 60),
            tpm=selected_model_settings.get("tpm", 60000),
        )
        self.MODEL_SETTINGS = {
            model_id: ModelSetting(
                id=model_family,
                endpoints=[endpoint],
                max_tokens=selected_model_settings.get("max_tokens", 8192),
                concurrent=selected_model_settings.get("concurrent", 1),
            )
        }
        super().__init__(workflow_data, node_id)
