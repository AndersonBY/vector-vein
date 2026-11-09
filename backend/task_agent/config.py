"""Shared, credential-free model snapshots for desktop tasks."""
from __future__ import annotations

from copy import deepcopy

from vv_agent.config import ConfigError, EndpointConfig, EndpointOption, ResolvedModelConfig, resolve_model_endpoint
from vv_agent.llm.vv_llm_client import EndpointTarget, VvLlmClient
from vv_agent.model import ModelError, ModelRef
from vv_agent.model_settings import ModelSettings

from utilities.config import Settings

MAX_CYCLE_LIMIT = 2**32 - 1


def current_llm_settings() -> dict:
    return deepcopy(Settings().data["llm_settings"])


def _backend_key(settings: dict, provider: str) -> str:
    backends = settings.get("backends", {})
    if provider.startswith("_local__") and "local" in backends:
        return "local"
    if provider in backends:
        return provider
    normalized = provider.strip().lower()
    if normalized in backends:
        return normalized
    compact = normalized.replace("_", "").replace(" ", "")
    for key in backends:
        if key.lower().replace("_", "") == compact:
            return key
    raise ConfigError("Selected model provider is not configured")


def build_model_snapshot(settings: dict, provider: str, model: str, reasoning_effort: str = "default") -> dict:
    if not isinstance(provider, str) or not provider.strip() or not isinstance(model, str) or not model.strip():
        raise ConfigError("Select a configured model before creating a task")
    if reasoning_effort != "default" and reasoning_effort not in {"none", "minimal", "low", "medium", "high", "xhigh", "max"}:
        raise ConfigError("Invalid reasoning effort")
    backend = _backend_key(settings, provider)
    resolved = resolve_model_endpoint(settings, backend=backend, model=model)
    capabilities = deepcopy(resolved.capabilities)
    configured = settings["backends"][backend]["models"][model].get("capabilities", {})
    if "reasoning_efforts" in configured and "supported_reasoning_efforts" not in capabilities:
        capabilities["supported_reasoning_efforts"] = deepcopy(configured["reasoning_efforts"])
    supported_efforts = capabilities.get("supported_reasoning_efforts")
    if reasoning_effort != "default" and isinstance(supported_efforts, list) and reasoning_effort not in supported_efforts:
        raise ConfigError("Selected reasoning effort is not supported by this model")
    return {
        "backend": resolved.backend,
        "display_provider": provider,
        "requested_model": resolved.requested_model,
        "selected_model": resolved.selected_model,
        "model_id": resolved.model_id,
        "context_length": resolved.context_length,
        "max_output_tokens": resolved.max_output_tokens,
        "function_call_available": resolved.function_call_available,
        "response_format_available": resolved.response_format_available,
        "native_multimodal": resolved.native_multimodal,
        "capabilities": capabilities,
        "reasoning_effort": reasoning_effort,
        "endpoint_options": [
            {
                "endpoint_id": option.endpoint.endpoint_id,
                "api_base": option.endpoint.api_base,
                "endpoint_type": option.endpoint.endpoint_type,
                "model_id": option.model_id,
                "requires_api_key": bool(option.endpoint.api_key),
            }
            for option in resolved.endpoint_options
        ],
    }


def resolve_snapshot(snapshot: dict, settings: dict) -> ResolvedModelConfig:
    try:
        endpoints = {item.get("id"): item for item in settings.get("endpoints", []) if isinstance(item, dict)}
        options = []
        for item in snapshot["endpoint_options"]:
            endpoint_id = item["endpoint_id"]
            current = endpoints.get(endpoint_id, {})
            api_key = str(current.get("api_key", "")).strip()
            if item.get("requires_api_key") and not api_key:
                raise ConfigError("An endpoint credential is no longer available")
            options.append(
                EndpointOption(
                    endpoint=EndpointConfig(
                        endpoint_id=endpoint_id,
                        api_key=api_key,
                        api_base=item["api_base"],
                        endpoint_type=item.get("endpoint_type", "default"),
                    ),
                    model_id=item["model_id"],
                )
            )
        if not options:
            raise ConfigError("Task model has no endpoint options")
        return ResolvedModelConfig(
            backend=snapshot["backend"],
            requested_model=snapshot["requested_model"],
            selected_model=snapshot["selected_model"],
            model_id=snapshot["model_id"],
            endpoint_options=options,
            context_length=snapshot.get("context_length"),
            max_output_tokens=snapshot.get("max_output_tokens"),
            function_call_available=snapshot.get("function_call_available") is True,
            response_format_available=snapshot.get("response_format_available") is True,
            native_multimodal=snapshot.get("native_multimodal") is True,
            capabilities=deepcopy(snapshot.get("capabilities", {})),
        )
    except (KeyError, TypeError) as exc:
        raise ConfigError("Invalid task model snapshot") from exc


class DesktopModelProvider:
    """Resolve snapshots without serializing endpoint credentials into tasks."""

    def __init__(self, settings_loader=current_llm_settings, *, default_backend: str | None = None, timeout_seconds: float = 90, snapshot: dict | None = None, on_failure=None, summary_alias: str | None = None):
        self.settings_loader = settings_loader
        self.default_backend = default_backend
        self.snapshot = deepcopy(snapshot)
        self.on_failure = on_failure
        self.timeout_seconds = timeout_seconds
        self.summary_alias = summary_alias

    def resolve(self, model: ModelRef) -> ResolvedModelConfig:
        if model.type == "resolved" and model.resolved_config is not None:
            return model.resolved_config
        settings = self.settings_loader()
        if model.type == "backend_model":
            if self.snapshot is not None and model.backend_id == self.snapshot["backend"] and model.model_name == self.summary_alias:
                return resolve_snapshot(self.snapshot, settings)
            return resolve_snapshot(build_model_snapshot(settings, model.backend_id, model.model_name), settings)
        if model.type != "named":
            raise ModelError("Unsupported task model reference")
        if self.snapshot is not None and model.model_name in {self.snapshot["requested_model"], self.snapshot["selected_model"], *[item["model_id"] for item in self.snapshot["endpoint_options"]]}:
            return resolve_snapshot(self.snapshot, settings)
        backend = self.default_backend
        if backend:
            return resolve_snapshot(build_model_snapshot(settings, backend, model.model_name), settings)
        matches = []
        for backend_id, config in settings.get("backends", {}).items():
            for key in config.get("models", {}):
                try:
                    snapshot = build_model_snapshot(settings, backend_id, key)
                except ConfigError:
                    continue
                if snapshot["model_id"] == model.model_name:
                    matches.append(snapshot)
        if len(matches) != 1:
            raise ModelError("Model ID must identify exactly one configured model")
        return resolve_snapshot(matches[0], settings)

    def client(self, resolved: ResolvedModelConfig) -> VvLlmClient:
        from .model_errors import DiagnosticLlmClient
        return DiagnosticLlmClient(
            on_failure=self.on_failure,
            backend=resolved.backend,
            selected_model=resolved.selected_model,
            endpoint_targets=[
                EndpointTarget(
                    endpoint_id=option.endpoint.endpoint_id,
                    api_key=option.endpoint.api_key,
                    api_base=option.endpoint.api_base,
                    endpoint_type=option.endpoint.endpoint_type,
                    model_id=option.model_id,
                )
                for option in resolved.endpoint_options
            ],
            timeout_seconds=self.timeout_seconds,
            randomize_endpoints=False,
        )

    def default_settings(self, resolved: ResolvedModelConfig) -> ModelSettings:
        del resolved
        effort = (self.snapshot or {}).get("reasoning_effort", "default")
        return ModelSettings(timeout_seconds=self.timeout_seconds, reasoning={"effort": effort} if effort != "default" else None)

    def default_model_ref(self) -> None:
        return None
