"""Frozen MCP identity distinguishes credential rotation from changing tool destinations."""
from copy import deepcopy

import pytest

from task_agent.integrations import mcp_endpoint_fingerprint


def remote_record():
    return {"transport": "streamable_http", "config": {}, "secrets": {
        "url": "https://mcp.example.invalid/mcp?project=alpha&token=credential-one",
        "headers": {"Authorization": "Bearer credential-one", "X-Tenant": "alpha"},
    }}


def test_query_routing_values_are_bound_to_the_frozen_endpoint():
    first = remote_record()
    changed = deepcopy(first)
    changed["secrets"]["url"] = changed["secrets"]["url"].replace("project=alpha", "project=beta")
    assert mcp_endpoint_fingerprint(first) != mcp_endpoint_fingerprint(changed)


def test_header_routing_values_are_bound_to_the_frozen_endpoint():
    first = remote_record()
    changed = deepcopy(first)
    changed["secrets"]["headers"]["X-Tenant"] = "beta"
    assert mcp_endpoint_fingerprint(first) != mcp_endpoint_fingerprint(changed)


def test_known_remote_credentials_can_rotate_without_rerouting():
    first = remote_record()
    changed = deepcopy(first)
    changed["secrets"]["url"] = changed["secrets"]["url"].replace("credential-one", "credential-two")
    changed["secrets"]["headers"]["Authorization"] = "Bearer credential-two"
    assert mcp_endpoint_fingerprint(first) == mcp_endpoint_fingerprint(changed)


@pytest.mark.parametrize("key", ["MONKEY_HOME", "TOKENIZER_CACHE_DIR", "SERVER_BASE_URL"])
def test_noncredential_environment_changes_cannot_be_hidden_by_substring_matching(key):
    first = {"transport": "stdio", "config": {"command": "python", "args": ["server.py"]},
             "secrets": {"env": {key: "first", "API_KEY": "credential-one"}}}
    changed = deepcopy(first)
    changed["secrets"]["env"][key] = "second"
    assert mcp_endpoint_fingerprint(first) != mcp_endpoint_fingerprint(changed)


def test_known_stdio_api_key_can_rotate_without_changing_server_identity():
    first = {"transport": "stdio", "config": {"command": "python", "args": ["server.py"]},
             "secrets": {"env": {"API_KEY": "credential-one", "SERVER_BASE_URL": "https://one.invalid"}}}
    changed = deepcopy(first)
    changed["secrets"]["env"]["API_KEY"] = "credential-two"
    assert mcp_endpoint_fingerprint(first) == mcp_endpoint_fingerprint(changed)
