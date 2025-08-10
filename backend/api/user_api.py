# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 02:02:39
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-07-13 12:05:07
import json
import time

import webview
from vectorvein.types import EndpointSetting

from .utils import JResponse
from models import Setting, Conversation, Agent, model_serializer
from utilities.general import LogServer
from tts_server.server import tts_server
from utilities.media_processing import Microphone
from utilities.shortcuts import shortcuts_listener
from utilities.media_processing import get_screenshot
from utilities.config import config, Settings, cache, DEFAULT_SETTINGS


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
    for agent_id, shortcut in _shortcuts.items():
        if shortcut["new_chat_with_agent"]:
            shortcuts_listener.register_hotkeys(shortcut["new_chat_with_agent"], lambda: start_chat(agent_id))
        if shortcut["new_chat_with_agent_with_screenshot"]:
            shortcuts_listener.register_hotkeys(
                shortcut["new_chat_with_agent_with_screenshot"],
                lambda: start_chat(agent_id, with_screenshot=True),
            )
        if shortcut["continue_chat_with_agent"]:
            shortcuts_listener.register_hotkeys(
                shortcut["continue_chat_with_agent"], lambda: start_chat(agent_id, continue_chat=True)
            )
        if shortcut["continue_chat_with_agent_with_screenshot"]:
            shortcuts_listener.register_hotkeys(
                shortcut["continue_chat_with_agent_with_screenshot"],
                lambda: start_chat(agent_id, continue_chat=True, with_screenshot=True),
            )
    shortcuts_listener.restart()


class SettingAPI:
    name = "setting"

    def get_default_settings(self, payload):
        return JResponse(data=DEFAULT_SETTINGS)

    def get(self, payload):
        if Setting.select().count() == 0:
            setting = Setting.create()
        else:
            setting = Setting.select().order_by(Setting.create_time.desc()).first()
        setting = model_serializer(setting)
        
        # Add API configuration to the response
        api_config = {
            "api": {
                "host": config.get("api.host", "127.0.0.1"),
                "port": config.get("api.port", 8787),
                "enabled": config.get("api.enabled", True),
                "current_url": cache.get("api_server_url", ""),
            }
        }
        
        return JResponse(data={**setting, **config, **api_config})

    def update(self, payload):
        setting_id = payload.get("id")
        setting = Setting.get_by_id(setting_id)
        setting.data = payload.get("data", {})
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
        endpoint = EndpointSetting(
            **{
                "id": "test-endpoint",
                "api_base": payload.get("base_url"),
                "api_key": payload.get("api_key"),
            }
        )
        models = endpoint.model_list()
        return JResponse(data={"models": models})


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
