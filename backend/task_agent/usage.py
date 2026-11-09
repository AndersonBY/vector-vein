"""Bounded token counters from provider-reported public model-call events."""
from __future__ import annotations


def count(value):
    return value if type(value) is int and 0 <= value <= 2**53 - 1 else None


def clean_usage(value):
    if not isinstance(value, dict):
        return None
    cache = value.get("cache_usage") or {}
    return {
        "input_tokens": count(value.get("input_tokens")),
        "output_tokens": count(value.get("output_tokens")),
        "cache_read_tokens": count(cache.get("read_input_tokens")) if isinstance(cache, dict) and cache.get("status") == "provider_reported" else None,
    }


def usage_summary(events):
    seen = set()
    calls = []
    for event in events:
        if event.get("kind") not in {"model_success", "model_failure"} or not isinstance(event.get("usage"), dict):
            continue
        identity = (event.get("turn_id"), event.get("call_id"), event.get("attempt", 1))
        if identity in seen:
            continue
        seen.add(identity)
        calls.append(event)
    prompt = [count(item["usage"].get("input_tokens")) for item in calls]
    output = [count(item["usage"].get("output_tokens")) for item in calls]
    cached = [(count(item["usage"].get("input_tokens")), count(item["usage"].get("cache_read_tokens"))) for item in calls]
    known_cache = [(total, hit) for total, hit in cached if total is not None and hit is not None and hit <= total]
    return {
        "input_tokens": sum(value for value in prompt if value is not None) if any(value is not None for value in prompt) else None,
        "output_tokens": sum(value for value in output if value is not None) if any(value is not None for value in output) else None,
        "latest_input_tokens": next((count(item["usage"].get("input_tokens")) for item in reversed(calls) if item.get("operation") == "agent_cycle" and count(item["usage"].get("input_tokens")) is not None), None),
        "cache_read_tokens": sum(hit for _, hit in known_cache) if known_cache else None,
        "cache_input_tokens": sum(total for total, _ in known_cache) if known_cache else None,
        "reported_calls": len(calls),
        "cache_missing_calls": len(calls) - len(known_cache),
    }
