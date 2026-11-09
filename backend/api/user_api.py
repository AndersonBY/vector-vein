# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 02:02:39
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-07-13 12:05:07
import json
import os
import time
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

import webview
from vv_llm.types import EndpointSetting

from .utils import JResponse
from models import Setting, model_serializer
from utilities.general import LogServer
from utilities.file_processing.files import read_file_content
from utilities.config import config, Settings, cache, DEFAULT_SETTINGS
from utilities.config.settings import normalize_embedding_backends, update_llm_settings_to_v2, validate_rerank_settings
from utilities.llm_endpoint_test import run_model_endpoint_test
from utilities.retrieval_model_test import RetrievalTestError, run_retrieval_model_test
from utilities.workflow_errors import redact_message


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
    """Register global workspace shortcuts."""
    # Import desktop input hooks only when registering or recording shortcuts.
    from utilities.shortcuts import shortcuts_listener

    if shortcuts is None:
        settings = Settings()
        _shortcuts: dict = settings.get("shortcuts", {})
    else:
        _shortcuts = shortcuts
    shortcuts_listener.clear_hotkeys()
    global_shortcut_actions = {
        "open_task_agent": lambda: push_route("taskAgentWorkbench"),
        "open_workflow_space": lambda: push_route("WorkflowSpaceMain"),
        "open_schedule_manager": lambda: push_route("WorkflowScheduleManager"),
        "open_data_space": lambda: push_route("DataSpaceMain"),
    }
    for action_name, callback in global_shortcut_actions.items():
        combo = _shortcuts.get("__global__", {}).get(action_name)
        if combo:
            shortcuts_listener.register_hotkeys(combo, callback)
    shortcuts_listener.restart()


_ENDPOINT_SECRET_FIELDS = ("api_key", "credentials", "access_token", "headers", "proxy")


def settings_for_ui(data):
    result = deepcopy(data)
    if os.environ.get("VECTORVEIN_LLM_SETTINGS_FILE"):
        # External credentials are runtime-only, including when the UI caches or saves settings.
        for endpoint in result.get("llm_settings", {}).get("endpoints", []):
            hidden = [key for key in _ENDPOINT_SECRET_FIELDS if endpoint.get(key)]
            endpoint["_saved_endpoint_id"] = endpoint["id"]
            endpoint["_saved_secret_fields"] = hidden
            for key in hidden:
                endpoint[key] = {} if key in {"credentials", "headers"} else ""
    return result


def resolve_endpoint_draft(draft, saved_endpoints=None):
    endpoint = deepcopy(draft)
    reference = endpoint.pop("_saved_endpoint_id", None)
    fields = endpoint.pop("_saved_secret_fields", [])
    if not fields:
        return endpoint
    if not isinstance(fields, list) or any(key not in _ENDPOINT_SECRET_FIELDS for key in fields):
        raise ValueError("Invalid saved endpoint credential reference.")
    if saved_endpoints is None:
        try:
            saved_endpoints = Settings().get("llm_settings", {}).get("endpoints", [])
        except Exception:
            raise ValueError("Unable to load saved endpoint configuration. Check the model settings file.") from None
    saved = next((item for item in saved_endpoints if item.get("id") == reference), None)
    if saved is None:
        raise ValueError("Saved endpoint no longer exists. Reopen settings and enter its credentials.")
    # Do not send stored credentials to a different destination from an edited draft.
    for key, default in (("api_base", ""), ("endpoint_type", "default"), ("proxy", ""), ("headers", {})):
        if not (key in fields and not endpoint.get(key)) and (endpoint.get(key) or default) != (saved.get(key) or default):
            raise ValueError("Endpoint address, adapter, proxy or headers changed. Re-enter credentials before testing or saving.")
    for key in fields:
        if not endpoint.get(key):
            endpoint[key] = deepcopy(saved.get(key))
    return endpoint


def save_external_llm_settings(llm_settings):
    path = Path(os.environ["VECTORVEIN_LLM_SETTINGS_FILE"])
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(llm_settings, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class SettingAPI:
    name = "setting"

    def test_notification(self, payload):
        from utilities.desktop_notifications import send_notification
        language = payload.get("language", "zh-CN")
        if language not in {"zh-CN", "en-US"}:
            return JResponse(status=400, msg="Invalid notification language")
        body = "这是一条 VectorVein 测试通知。" if language == "zh-CN" else "This is a VectorVein test notification."
        sent = send_notification("VectorVein", body)
        return JResponse(status=200 if sent else 503, data={"submitted": sent}, msg="" if sent else "Desktop notifications unavailable")

    def attachment_image(self, payload):
        from utilities.attachment_preview import AttachmentPreviewError, attachment_image_url
        try:
            return JResponse(data={"url": attachment_image_url(payload)})
        except AttachmentPreviewError as error:
            return JResponse(status=error.status, msg=str(error))

    def get_default_settings(self, payload):
        return JResponse(data=deepcopy(DEFAULT_SETTINGS))

    def get(self, payload):
        normalized_settings = Settings()
        if Setting.select().count() == 0:
            setting = Setting.create()
        else:
            setting = Setting.select().order_by(Setting.create_time.desc()).first()
        setting_payload = model_serializer(setting)
        setting_payload["data"] = settings_for_ui(normalized_settings.data)
        
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
        setting_data = deepcopy(payload.get("data", {}))
        if not isinstance(setting_data, dict):
            setting_data = {}
        if "notifications" in setting_data:
            from utilities.desktop_notifications import validate_notification_settings
            try:
                setting_data["notifications"] = validate_notification_settings(setting_data["notifications"])
            except ValueError:
                return JResponse(status=400, msg="Invalid notification settings")
        external = os.environ.get("VECTORVEIN_LLM_SETTINGS_FILE")
        if external:
            try:
                current_llm = Settings().get("llm_settings", {})
            except Exception:
                return JResponse(status=500, msg="Unable to load saved endpoint configuration. Check the model settings file.")
            try:
                llm_settings = setting_data.get("llm_settings", {})
                # Resolve references before vv-llm normalization drops UI-only fields.
                llm_settings["endpoints"] = [resolve_endpoint_draft(item, current_llm.get("endpoints", []))
                                             for item in llm_settings.get("endpoints", [])]
            except ValueError as error:
                return JResponse(status=400, msg=redact_message(error, {"credentials": setting_data}, include_settings=False))
        try:
            setting_data = update_llm_settings_to_v2(setting_data)
            normalize_embedding_backends(setting_data)
            validate_rerank_settings(setting_data)
        except ValueError as error:
            return JResponse(status=400, msg=redact_message(error, {"credentials": setting_data}, include_settings=False))
        from utilities.model_selection import validate_model_preferences
        try:
            validate_model_preferences(setting_data)
        except ValueError as error:
            return JResponse(status=400, msg=str(error))
        if external:
            try:
                llm_settings = setting_data.get("llm_settings", {})
                from vv_llm.settings import Settings as LlmSettings
                LlmSettings.model_validate(llm_settings)
                current = update_llm_settings_to_v2({"settings_version": 2, "llm_settings": deepcopy(current_llm)})
                normalize_embedding_backends(current)
                if llm_settings != current["llm_settings"]:
                    save_external_llm_settings(llm_settings)
            except Exception as error:
                return JResponse(status=400 if isinstance(error, ValueError) else 500,
                                 msg=redact_message(error, {"credentials": [setting_data, llm_settings]}, include_settings=False))
            setting_data["llm_settings"] = deepcopy(setting.data.get("llm_settings", {}))
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
        response = model_serializer(setting)
        if os.environ.get("VECTORVEIN_LLM_SETTINGS_FILE"):
            response["data"] = settings_for_ui(Settings().data)
        return JResponse(data=response)

    def list(self, payload):
        settings = Setting.select().order_by(Setting.create_time.desc())
        settings_list = model_serializer(settings, many=True)
        return JResponse(data=settings_list)

    def get_window_setting(self, payload):
        from utilities.desktop_window import window_settings
        return JResponse(data=window_settings())

    def minimize_to_tray(self, payload):
        from utilities.desktop_window import get_controller
        controller = get_controller()
        if controller is None:
            return JResponse(status=503, msg="System tray unavailable")
        try:
            controller.minimize_to_tray()
        except Exception:
            return JResponse(status=503, msg="System tray unavailable")
        return JResponse()

    def update_window_setting(self, payload):
        if "close_action" in payload:
            from utilities.desktop_window import save_close_action, window_settings
            try:
                save_close_action(payload["close_action"])
            except ValueError:
                return JResponse(status=400, msg="Invalid window close action")
            return JResponse(data=window_settings())
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
        resolved = payload
        try:
            resolved = resolve_endpoint_draft(payload["endpoint"]) if "endpoint" in payload else {
                "id": "test-endpoint", "api_base": payload.get("base_url"), "api_key": payload.get("api_key"),
            }
            endpoint = EndpointSetting.model_validate(resolved)
            models = endpoint.model_list()
            return JResponse(data={"models": models})
        except Exception as error:
            return JResponse(status=400 if isinstance(error, ValueError) else 500,
                             msg=redact_message(error, {"credentials": [payload, resolved]}, include_settings=False))

    def test_model_endpoint(self, payload):
        resolved = payload
        try:
            if isinstance(payload, dict) and isinstance(payload.get("endpoint"), dict):
                resolved = {**payload, "endpoint": resolve_endpoint_draft(payload["endpoint"])}
            return JResponse(data=run_model_endpoint_test(resolved))
        except Exception as error:
            return JResponse(
                status=400 if isinstance(error, ValueError) else 502,
                msg=redact_message(error, {"credentials": [payload, resolved]}, include_settings=False),
            )

    def test_retrieval_model(self, payload):
        try:
            if isinstance(payload, dict) and isinstance(payload.get("endpoint"), dict):
                payload = {**payload, "endpoint": resolve_endpoint_draft(payload["endpoint"])}
            return JResponse(data=run_retrieval_model_test(payload))
        except RetrievalTestError as error:
            return JResponse(status=error.status, data={"error_code": error.code}, msg=str(error))
        except Exception:
            error = RetrievalTestError("invalid_config")
            return JResponse(status=error.status, data={"error_code": error.code}, msg=str(error))

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


class ShortcutAPI:
    name = "shortcut"

    def list(self, payload):
        shortcuts = Settings().get("shortcuts", {})
        return JResponse(data=shortcuts)

    def set_setting_mode(self, payload):
        from utilities.shortcuts import shortcuts_listener

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
