# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 02:02:39
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-07-13 12:05:07
import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

import webview
from vv_llm.types import EndpointSetting

from .utils import JResponse
from models import Setting, Conversation, Agent, model_serializer
from utilities.general import LogServer
from tts_server.server import tts_server
from utilities.media_processing import Microphone
from utilities.shortcuts import shortcuts_listener
from utilities.media_processing import get_screenshot
from utilities.file_processing.files import read_file_content
from utilities.config import config, Settings, cache, DEFAULT_SETTINGS
from utilities.config.settings import normalize_embedding_backends, update_llm_settings_to_v2


def start_chat(agent_id: str, continue_chat: bool = False, with_screenshot: bool = False):
    if continue_chat:
        agent = Agent.select().where(Agent.aid == agent_id).first()
        conversation = (
            Conversation.select().where(Conversation.agent == agent).order_by(Conversation.update_time.desc()).first()
        )
        conversation_id = conversation.cid.hex
        if not conversation_id:
            router_push_params = json.dumps({"name": "conversationNew", "params": {"agentId": agent_id}})
        else:
            router_push_params = json.dumps(
                {"name": "conversationDetail", "params": {"agentId": agent_id, "conversationId": conversation_id}}
            )
    else:
        router_push_params = json.dumps({"name": "conversationNew", "params": {"agentId": agent_id}})

    has_start_recording = cache.get("has_start_recording")
    if not has_start_recording and with_screenshot:
        settings = Settings()
        monitor_number = int(settings.get("agent.screenshot_monitor_device", 0))
        screen_shot_path = [get_screenshot(output_type="file_path", monitor_number=monitor_number)]
        cache.set(f"screen_shot_path_{agent_id}", screen_shot_path, expire=600)
    else:
        screen_shot_path = cache.get(f"screen_shot_path_{agent_id}", []) if with_screenshot else []

    function_name = "start_recording" if not has_start_recording else "stop_recording"
    window = webview.windows[0]
    window.evaluate_js(f"window.router.push({router_push_params})")
    window.evaluate_js(
        f"""
        const mainFunction = async () => {{
            while (!window.{function_name} || !window.setAttachments) {{
                await new Promise((resolve) => setTimeout(resolve, 100))
            }}
            window.setAttachments({json.dumps(screen_shot_path)})
            {function_name}({{auto_stop: true}})
        }}
        mainFunction()
        """
    )
    if has_start_recording:
        cache.delete("has_start_recording")
        cache.delete(f"screen_shot_path_{agent_id}")
    else:
        cache.set("has_start_recording", True, expire=600)


def push_route(route_name: str, params: dict | None = None, query: dict | None = None):
    if not webview.windows:
        return
    route_payload: dict[str, Any] = {"name": route_name}
    if params:
        route_payload["params"] = params
    if query:
        route_payload["query"] = query
    webview.windows[0].evaluate_js(f"window.router.push({json.dumps(route_payload)})")


def _resolve_existing_directory(raw_path: str | None):
    if not raw_path:
        return None
    try:
        path = Path(raw_path).expanduser().resolve()
    except Exception:
        return None
    if path.exists() and path.is_dir():
        return path
    return None


def _serialize_fs_entry(path: Path):
    stat = path.stat()
    return {
        "name": path.name,
        "path": path.as_posix(),
        "is_dir": path.is_dir(),
        "size_bytes": 0 if path.is_dir() else stat.st_size,
        "modified_time": int(stat.st_mtime * 1000),
    }


def _list_directory_entries(path: Path, limit: int = 200):
    entries = []
    for item in path.iterdir():
        try:
            item.stat()
            entries.append(item)
        except Exception:
            continue
    entries.sort(key=lambda item: (not item.is_dir(), -item.stat().st_mtime, item.name.lower()))
    return [_serialize_fs_entry(item) for item in entries[:limit]]


def _scan_recent_files(roots: list[Path], limit: int = 24):
    candidates = []
    for root in roots:
        try:
            iterator = root.rglob("*")
        except Exception:
            continue
        for item in iterator:
            try:
                if not item.is_file():
                    continue
                if any(part.startswith(".") for part in item.parts):
                    continue
                if any(part in {"cache", "__pycache__", "qdrant_db"} for part in item.parts):
                    continue
                item.stat()
                candidates.append(item)
            except Exception:
                continue
    candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return [_serialize_fs_entry(item) for item in candidates[:limit]]


def register_shortcuts(shortcuts: dict | None = None):
    """Register shortcuts and restart shortcuts_listener.

    Args:
        shortcuts (dict | None, optional): Should be a dict like:
        ```python
        {
            "agent1_id": {
                "new_chat_with_agent": "<shortcuts combo>",
                "new_chat_with_agent_with_screenshot": "<shortcuts combo>",
                "continue_chat_with_agent": "<shortcuts combo>",
                "continue_chat_with_agent_with_screenshot": "<shortcuts combo>"
            }
        }
        ```
    """
    if shortcuts is None:
        settings = Settings()
        _shortcuts: dict = settings.get("shortcuts", {})
    else:
        _shortcuts = shortcuts
    shortcuts_listener.clear_hotkeys()
    global_shortcut_actions = {
        "open_workflow_space": lambda: push_route("WorkflowSpaceMain"),
        "open_schedule_manager": lambda: push_route("WorkflowScheduleManager"),
        "open_data_space": lambda: push_route("DataSpaceMain"),
    }
    for agent_id, shortcut in _shortcuts.items():
        if agent_id == "__global__":
            for action_name, callback in global_shortcut_actions.items():
                combo = shortcut.get(action_name)
                if combo:
                    shortcuts_listener.register_hotkeys(combo, callback)
            continue

        if shortcut.get("new_chat_with_agent"):
            shortcuts_listener.register_hotkeys(
                shortcut["new_chat_with_agent"],
                lambda current_agent_id=agent_id: start_chat(current_agent_id),
            )
        if shortcut.get("new_chat_with_agent_with_screenshot"):
            shortcuts_listener.register_hotkeys(
                shortcut["new_chat_with_agent_with_screenshot"],
                lambda current_agent_id=agent_id: start_chat(current_agent_id, with_screenshot=True),
            )
        if shortcut.get("continue_chat_with_agent"):
            shortcuts_listener.register_hotkeys(
                shortcut["continue_chat_with_agent"],
                lambda current_agent_id=agent_id: start_chat(current_agent_id, continue_chat=True),
            )
        if shortcut.get("continue_chat_with_agent_with_screenshot"):
            shortcuts_listener.register_hotkeys(
                shortcut["continue_chat_with_agent_with_screenshot"],
                lambda current_agent_id=agent_id: start_chat(current_agent_id, continue_chat=True, with_screenshot=True),
            )
    shortcuts_listener.restart()


class SettingAPI:
    name = "setting"

    def get_default_settings(self, payload):
        return JResponse(data=deepcopy(DEFAULT_SETTINGS))

    def get(self, payload):
        normalized_settings = Settings()
        if Setting.select().count() == 0:
            setting = Setting.create()
        else:
            setting = Setting.select().order_by(Setting.create_time.desc()).first()
        setting_payload = model_serializer(setting)
        setting_payload["data"] = normalized_settings.data
        
        # Add API configuration to the response
        api_config = {
            "api": {
                "host": config.get("api.host", "127.0.0.1"),
                "port": config.get("api.port", 8787),
                "enabled": config.get("api.enabled", True),
                "current_url": cache.get("api_server_url", ""),
            }
        }
        
        return JResponse(data={**setting_payload, **config, **api_config})

    def update(self, payload):
        setting_id = payload.get("id")
        setting = Setting.get_by_id(setting_id)
        setting_data = payload.get("data", {})
        if not isinstance(setting_data, dict):
            setting_data = {}
        setting_data = update_llm_settings_to_v2(setting_data)
        normalize_embedding_backends(setting_data)
        setting.data = setting_data
        setting.save()
        config.save("data_path", setting.data.get("data_path", "./data"))
        
        # Save API settings
        api_settings = setting.data.get("api", {})
        if api_settings:
            config.save("api.host", api_settings.get("host", "127.0.0.1"))
            config.save("api.port", api_settings.get("port", 8787))
            config.save("api.enabled", api_settings.get("enabled", True))
        
        if payload.get("update_shortcuts"):
            register_shortcuts(setting.data.get("shortcuts", {}))
        return JResponse(data=model_serializer(setting))

    def list(self, payload):
        settings = Setting.select().order_by(Setting.create_time.desc())
        settings_list = model_serializer(settings, many=True)
        return JResponse(data=settings_list)

    def update_window_setting(self, payload):
        window = webview.windows[0]
        time.sleep(0.1)  # If we don't sleep, the window will get frozen. Have no idea.
        pin_window = payload.get("pin_window")
        if pin_window is not None:
            window.on_top = pin_window
            config.save("window.on_top", pin_window)
        return JResponse()

    def update_config(self, payload):
        key = payload.get("key")
        value = payload.get("value")
        config.save(key, value)
        return JResponse()

    def get_port(self, payload):
        port_name = payload.get("port_name")
        port = cache.get(port_name)
        return JResponse(data={"port": port})

    def list_models(self, payload):
        try:
            base_url = payload.get("base_url")
            api_key = payload.get("api_key")
            endpoint = EndpointSetting(
                id="test-endpoint",
                api_base=base_url if isinstance(base_url, str) else None,
                api_key=api_key if isinstance(api_key, str) else None,
            )
            models = endpoint.model_list()
            return JResponse(data={"models": models})
        except Exception as error:
            return JResponse(status=500, msg=str(error))

    def read_local_document(self, payload):
        file_path = payload.get("file", "")
        if not file_path:
            return JResponse(status=400, msg="file is required")
        try:
            content = read_file_content(file_path, read_zip=True)
        except Exception as error:
            return JResponse(status=500, msg=str(error))
        return JResponse(
            data={
                "file": file_path,
                "content": content,
            }
        )

    def workspace_snapshot(self, payload):
        settings = Settings()
        roots = []
        for raw_path in [settings.get("data_path", "./data"), settings.get("output_folder", "./")]:
            root = _resolve_existing_directory(raw_path)
            if root and root not in roots:
                roots.append(root)

        current_path = _resolve_existing_directory(payload.get("path"))
        if current_path is None:
            current_path = roots[0] if roots else Path.cwd()

        parent_path = current_path.parent if current_path.parent != current_path else None
        return JResponse(
            data={
                "current_path": current_path.as_posix(),
                "parent_path": parent_path.as_posix() if parent_path else "",
                "roots": [_serialize_fs_entry(root) for root in roots],
                "entries": _list_directory_entries(current_path),
                "recent_files": _scan_recent_files(roots or [current_path]),
            }
        )


class HardwareAPI:
    name = "hardware"

    def list_microphones(self, payload):
        mic = Microphone()
        microphones = mic.list_devices()
        mic.close()
        return JResponse(data=microphones)

    def check_microphone(self, payload):
        if not self.mic.is_recording:
            cache.delete("has_start_recording")
        return JResponse(data={"is_recording": self.mic.is_recording, "audio_path": self.mic.latest_saved_file})

    def start_microphone(self, payload):
        tts_server.stop()
        settings = Settings()
        self.mic = Microphone(device_index=settings.get("microphone_device", 0))
        try:
            self.mic.start(auto_stop=payload.get("auto_stop", False))
            return JResponse()
        except Exception as e:
            return JResponse(msg=str(e))

    def stop_microphone(self, payload):
        try:
            cache.delete("has_start_recording")
            audio_path = self.mic.stop()
            return JResponse(data={"audio_path": audio_path})
        except Exception as e:
            return JResponse(status=500, msg=str(e))


class ShortcutAPI:
    name = "shortcut"

    def list(self, payload):
        shortcuts = Settings().get("shortcuts", {})
        return JResponse(data=shortcuts)

    def set_setting_mode(self, payload):
        def finish_setting_mode(payload):
            key_combination = []
            for key in payload:
                if hasattr(key, "name"):
                    key_combination.append(key.name.removesuffix("_l").removesuffix("_r"))
                else:
                    key_combination.append(key.char.upper())
            cache.set("shortcut_setting_mode_result", key_combination, expire=60)

        shortcuts_listener.set_setting_mode(finish_setting_mode)
        return JResponse()

    def get_setting_mode(self, payload):
        if cache.get("shortcut_setting_mode_result"):
            result = cache.get("shortcut_setting_mode_result")
            cache.delete("shortcut_setting_mode_result")
            return JResponse(data=result)
        else:
            return JResponse(status=404)


class LogAPI:
    name = "log"

    def get_log_content(self, payload):
        log_id = payload.get("log_id", "default")
        log_content = LogServer.get_log_content_by_id(log_id)
        return JResponse(data={"content": "\n".join(log_content)})
