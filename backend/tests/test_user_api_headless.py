from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_settings_api_loads_without_desktop_and_shortcuts_load_when_used(tmp_path):
    script = r'''
import importlib.abc
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, sys.argv[1])

class NoDesktop(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "utilities.shortcuts" or fullname.split(".")[0] == "pynput":
            raise ImportError("No display server available")

sys.meta_path.insert(0, NoDesktop())
from api import user_api
from models import database
from utilities.config import cache, config

try:
    api = user_api.SettingAPI()
    assert api.get_default_settings({})["status"] == 200
    assert api.attachment_image({})["status"] == 400
    assert api.test_model_endpoint({})["status"] == 400
    assert "utilities.shortcuts" not in sys.modules
    assert "pynput" not in sys.modules

    shortcuts = ModuleType("utilities.shortcuts")
    listener = shortcuts.shortcuts_listener = Mock()
    with patch.dict(sys.modules, {"utilities.shortcuts": shortcuts}), \
         patch.object(user_api, "push_route") as push_route, \
         patch.object(user_api, "start_chat") as start_chat:
        user_api.register_shortcuts({
            "__global__": {"open_workflow_space": "<ctrl>+1"},
            "agent": {"new_chat_with_agent": "<ctrl>+2"},
        })
        listener.clear_hotkeys.assert_called_once_with()
        listener.restart.assert_called_once_with()
        calls = listener.register_hotkeys.call_args_list
        assert [call.args[0] for call in calls] == ["<ctrl>+1", "<ctrl>+2"]
        calls[0].args[1]()
        calls[1].args[1]()
        push_route.assert_called_once_with("WorkflowSpaceMain")
        start_chat.assert_called_once_with("agent")

        shortcut_api = user_api.ShortcutAPI()
        assert shortcut_api.set_setting_mode({})["status"] == 200
        listener.set_setting_mode.assert_called_once()
        listener.set_setting_mode.call_args.args[0]([
            SimpleNamespace(name="ctrl_l"), SimpleNamespace(char="a"),
        ])
        assert shortcut_api.get_setting_mode({})["data"] == ["ctrl", "A"]
        assert shortcut_api.get_setting_mode({})["status"] == 404
    assert "pynput" not in sys.modules
finally:
    cache.close()
    config.close()
    database.close()
'''
    environment = {key: value for key, value in os.environ.items()
                   if key not in ("VECTORVEIN_LLM_SETTINGS_FILE", "VECTORVEIN_OUTPUT_DIR")}
    process = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", script, str(Path(__file__).resolve().parents[1])],
        cwd=tmp_path, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert process.returncode == 0, process.stderr + process.stdout
