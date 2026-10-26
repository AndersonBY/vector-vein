from vv_llm.types import ModelSetting

from utilities.workflow_errors import WorkflowInputError


def validate_workflow_model(model: ModelSetting, *, tools=False, json_object=False, images=False, max_output_tokens=0) -> ModelSetting:
    for requested, available, capability in (
        (tools, model.function_call_available, "function calling"),
        (json_object, model.response_format_available, "JSON object mode"),
        (images, model.native_multimodal, "image input"),
    ):
        if requested and not available:
            raise WorkflowInputError(f"Configured model {model.id} does not support {capability}")
    if max_output_tokens:
        try:
            budget = int(max_output_tokens)
        except (TypeError, ValueError):
            raise WorkflowInputError("Output token limit must be an integer") from None
        if isinstance(max_output_tokens, bool) or (isinstance(max_output_tokens, float) and max_output_tokens != budget):
            raise WorkflowInputError("Output token limit must be an integer")
        if not 1 <= budget <= model.context_length:
            raise WorkflowInputError("Output token limit must fit the model context")
        if model.max_output_tokens is not None and budget > model.max_output_tokens:
            raise WorkflowInputError("Output token limit exceeds the configured model maximum")
        return model.model_copy(update={"max_output_tokens": budget})
    return model
