from vv_llm.types import NOT_GIVEN

REASONING_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max"}


def parse_reasoning_effort(value):
    if value is None or value == "" or value == "default":
        return NOT_GIVEN
    if not isinstance(value, str) or value not in REASONING_EFFORTS:
        raise ValueError("Invalid reasoning effort")
    return value


def validate_model_preferences(data):
    preferences = data.get("model_preferences", {})
    if not isinstance(preferences, dict) or set(preferences) - {"default", "high_performance", "low_cost"}:
        raise ValueError("Invalid model presets")
    backends = data.get("llm_settings", {}).get("backends", {})
    for preset in preferences.values():
        if not isinstance(preset, dict):
            raise ValueError("Each model preset must be an object")
        provider, model = preset.get("model_provider", ""), preset.get("model", "")
        if not isinstance(provider, str) or not isinstance(model, str):
            raise ValueError("Model presets require string provider and model values")
        if not provider and not model:
            continue
        backend = "local" if provider.startswith("_local__") else provider.lower()
        configured = backends.get(backend, {}).get("models", {}).get(model)
        if provider.startswith("_local__") and model not in data.get("custom_llms", {}).get(provider[len("_local__"):], []):
            raise ValueError("Model preset is not in the selected local family")
        # Legacy local families can predate local backend metadata.
        legacy_local = provider.startswith("_local__") and configured is None
        if not provider or not model or (not legacy_local and (not isinstance(configured, dict) or configured.get("enabled") is False)):
            raise ValueError("Model presets must use an enabled model")
