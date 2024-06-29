# @Author: Bi Ying
# @Date:   2024-06-07 00:04:13
from utilities.config import Settings


MULTIMOAL_MODELS = [
    "gpt-4",
    "gpt-4o",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
    "yi-vision",
    "glm-4v",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
]


def check_multimodal_available(model: str, backend: str = None):
    if model in MULTIMOAL_MODELS:
        return True
    if backend is not None and backend.startswith("_local__"):
        backend = backend.removeprefix("_local__")
        settings = Settings()
        family_settings = next((item for item in settings.local_llms if item["model_family"].lower() == backend), None)
        if family_settings is None:
            return False
        model_settings = next(
            (item for item in family_settings["models"] if item["model_id"].lower() == model.lower()), None
        )
        if model_settings is None:
            return False
        return model_settings.get("native_multimodal", False)
    return False


def get_tool_call_data(tool_call_data: dict, simple: bool = False):
    tools = tool_call_data.get("workflows", []) + tool_call_data.get("templates", [])
    if simple:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            }
            for tool in tools
            if "name" in tool
        ]
    else:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("parameters", {}),
                },
            }
            for tool in tools
            if "name" in tool
        ]


def get_tool_related_workflow(
    conversation_data: dict,
    tool_call_data: dict,
    function_name: str,
):
    workflow_type = "Workflow"
    selected_tool = {}
    for tool in tool_call_data.get("workflows", []):
        if tool["name"] == function_name:
            selected_tool = tool
            break

    if not selected_tool:
        for tool in tool_call_data.get("templates", []):
            if tool["name"] == function_name:
                selected_tool = tool
                workflow_type = "WorkflowTemplate"
                break

    if workflow_type == "Workflow":
        related_workflows = conversation_data["related_workflows"]
        for workflow in related_workflows:
            if workflow["wid"] == selected_tool["workflow_id"]:
                return {
                    **workflow,
                    "type": workflow_type,
                }
    else:
        related_templates = conversation_data["related_templates"]
        for template in related_templates:
            if template["tid"] == selected_tool["workflow_id"]:
                return {
                    **template,
                    "type": workflow_type,
                }
