"""Bridge diagnostics may name operations but must never log integration credentials."""
import pytest


@pytest.mark.parametrize("fails", [False, True])
def test_bridge_debug_logging_excludes_secret_payloads_and_exception_text(monkeypatch, fails):
    import api_bridge

    logs = []
    secret = "SYNTHETIC_MCP_BRIDGE_SECRET_VALUE"
    monkeypatch.setattr(api_bridge, "mprint", logs.append)

    def save(payload):
        if fails:
            raise RuntimeError("Synthetic failure with private value: " + secret)
        return {"saved": True}

    method = "task_agent__save_mcp_server"
    monkeypatch.setattr(api_bridge.API, method, staticmethod(save), raising=False)
    payload = {"headers": {"Authorization": "Bearer " + secret}, "env": {"API_KEY": secret}}
    if fails:
        with pytest.raises(RuntimeError):
            api_bridge.API.debug_api_call(method, payload)
    else:
        assert api_bridge.API.debug_api_call(method, payload) == {"saved": True}
    assert logs
    assert any(method in line for line in logs)
    assert all(secret not in line for line in logs)
