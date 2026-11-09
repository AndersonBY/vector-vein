"""Run the desktop Task Agent App Server over stdio."""
from __future__ import annotations

import os
from pathlib import Path

from vv_agent.app_server import AppServer, StdioJsonlTransport
from vv_agent.session.sqlite import SQLiteStore

from utilities.config import config
from .host import DesktopTaskAgentHost


def serve() -> int:
    data_path = Path(config.data_path).resolve()
    task_root = data_path / "task-agent"
    task_root.mkdir(parents=True, exist_ok=True)
    os.environ["VV_AGENT_PRIVATE_ARTIFACT_ROOT"] = str(task_root / "retained")
    host = DesktopTaskAgentHost(task_root)
    store = SQLiteStore(str(task_root / "sessions.db"))
    server = AppServer(transport=StdioJsonlTransport(), host=host, store=store)
    try:
        server.run_forever()
    finally:
        from contextlib import suppress
        with suppress(Exception):
            host.shutdown()
        if os.name == "nt":
            with suppress(Exception):
                from .windows_commands import command_manager
                command_manager.shutdown()
        with suppress(Exception):
            server.kernel.close()
        with suppress(Exception):
            store.connection.close()
    return 0
