from vv_llm.settings import order_endpoints


def available_workflow_endpoints(settings, bindings):
    available = []
    for binding in bindings:
        if isinstance(binding, dict) and binding.get("enabled") is False:
            continue
        endpoint_id = binding["endpoint_id"] if isinstance(binding, dict) else binding
        try:
            endpoint = settings.get_endpoint(endpoint_id)
        except ValueError:
            continue
        if getattr(endpoint, "enabled", True):
            available.append(binding)
    return order_endpoints(available)


def bind_workflow_endpoint(client, endpoint, binding, model_id):
    # Provider clients cache their transport configuration per endpoint.
    if getattr(getattr(client, "endpoint", None), "id", None) != endpoint.id:
        client.__dict__.pop("raw_client", None)
    if hasattr(client, "backend_settings"):
        backend = client.backend_settings
        model = backend.models[client.model].model_copy(update={"endpoints": [binding]})
        client.backend_settings = backend.model_copy(update={"models": {**backend.models, client.model: model}})
    client.endpoint = endpoint
    client.endpoint_id = endpoint.id
    options = binding if isinstance(binding, dict) else {}
    client.model_id = options.get("model_id") or model_id
    for name in ("rpm", "tpm", "concurrent_requests"):
        setattr(client, name, options.get(name))
