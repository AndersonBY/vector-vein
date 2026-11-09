"""Only Task Agent and shared workspaces remain registered."""
import os
from pathlib import Path
import subprocess
import sys


def test_only_task_agent_is_registered_without_chat_schema(tmp_path):
    script = r'''
import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

sys.path.insert(0, sys.argv[1])
from models import create_tables, database
from utilities.config import cache, config

try:
    create_tables()
    assert not {"agent", "conversation", "message", "chatdraft"} & set(database.get_tables())
    from api_bridge import APIBridge
    bridge = APIBridge()
    assert not {"agent", "conversation", "message", "audio", "hardware"} & bridge.api_classes.keys()
    assert {"task_agent", "workflow", "setting", "shortcut"} <= bridge.api_classes.keys()
    assert not any(name.startswith(("agent__", "conversation__", "message__", "audio__", "hardware__")) for name in dir(bridge))
    for action in ("list_agents", "get_agent", "duplicate_agent"):
        assert not hasattr(bridge, "official_site__" + action)
    from workflow_stream.server import WebSocketServer
    server = WebSocketServer(host="127.0.0.1", start_port=0)
    assert set(server.handlers) == {"/ws/workflow_node"}
    for path in ("/ws/chat/removed", "/ws/chat", "/"):
        socket = SimpleNamespace(request=SimpleNamespace(path=path), close=AsyncMock())
        asyncio.run(server.handler(socket))
        socket.close.assert_awaited_once_with(1008, "Path not supported")
    print("retirement checks passed")
finally:
    cache.close()
    database.close()
    config.close()
'''
    environment = {key: value for key, value in os.environ.items()
                   if key not in ("VECTORVEIN_LLM_SETTINGS_FILE", "VECTORVEIN_OUTPUT_DIR")}
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", script, str(Path(__file__).resolve().parents[1])],
        cwd=tmp_path, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "retirement checks passed" in result.stdout
