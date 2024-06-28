# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-14 23:56:32
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-28 17:06:50
import os
import time
import queue
import threading
from pathlib import Path

import mimetypes
import webview
from webview.dom import DOMEventHandler

from api import API
from api.workflow_api import (
    WorkflowAPI,
    WorkflowTagAPI,
    WorkflowTemplateAPI,
    WorkflowRunRecordAPI,
    WorkflowRunScheduleAPI,
)
from api.vector_database_api import DatabaseAPI, DatabaseObjectAPI
from api.relational_database_api import (
    RelationalDatabaseAPI,
    RelationalDatabaseTableAPI,
    RelationalDatabaseTableRecordAPI,
)
from api.agent_api import (
    AudioAPI,
    AgentAPI,
    MessageAPI,
    ConversationAPI,
)
from api.user_api import (
    SettingAPI,
    HardwareAPI,
    ShortcutAPI,
    register_shortcuts,
)
from api.remote_api import OfficialSiteAPI
from utilities.config import config, cache
from utilities.general import LogServer, mprint
from utilities.shortcuts import shortcuts_listener
from utilities.network import proxies_for_requests
from utilities.file_processing import static_file_server
from models import create_tables, run_migrations
from worker import workflow_worker
from chat_server.server import WebSocketServer
from background_task.server import BackgroundTaskServer


def main():
    # Some mimetypes are not correctly registered in Windows. Register them manually.
    mimetypes.add_type("application/javascript", ".js")

    data_path = Path(config.data_path)
    if not data_path.exists():
        data_path.mkdir()
        (data_path / "static").mkdir()
        (data_path / "static" / "images").mkdir()

    # Create SQLite tables. Will ignore if tables already exist.
    run_migrations()
    create_tables()

    if Path("./DEBUG").exists():
        DEBUG = Path("./DEBUG").read_text() == "1"
    else:
        DEBUG = os.environ.get("VECTORVEIN_DEBUG", "0") == "1"
    if Path("./version.txt").exists():
        VERSION = Path("./version.txt").read_text()
    else:
        VERSION = os.environ.get("VECTORVEIN_VERSION", "0.0.1")

    def open_file_dialog(self, multiple=False):
        result = window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=multiple)
        return result

    def open_folder_dialog(self, initial_directory=""):
        result = window.create_file_dialog(webview.FOLDER_DIALOG, directory=initial_directory)
        return result

    def get_drop_file_path(self, file_name):
        start_time = time.time()
        while time.time() - start_time < 5:
            file_paths = cache.get(f"drop_file_{file_name}")
            if file_paths:
                cache.delete(f"drop_file_{file_name}")
                return file_paths
            time.sleep(0.1)
        return []

    task_queue = queue.Queue()
    api = API(DEBUG, VERSION, task_queue)
    api_class_list = [
        WorkflowAPI,
        WorkflowTagAPI,
        WorkflowTemplateAPI,
        WorkflowRunRecordAPI,
        WorkflowRunScheduleAPI,
        DatabaseAPI,
        DatabaseObjectAPI,
        RelationalDatabaseAPI,
        RelationalDatabaseTableAPI,
        RelationalDatabaseTableRecordAPI,
        SettingAPI,
        OfficialSiteAPI,
        AudioAPI,
        AgentAPI,
        MessageAPI,
        ConversationAPI,
        HardwareAPI,
        ShortcutAPI,
    ]
    for api_class in api_class_list:
        api.add_apis(api_class)
    setattr(API, "open_file_dialog", open_file_dialog)
    setattr(API, "open_folder_dialog", open_folder_dialog)
    setattr(API, "get_drop_file_path", get_drop_file_path)

    _proxies_for_requests = proxies_for_requests()

    if "http" in _proxies_for_requests:
        os.environ["http_proxy"] = _proxies_for_requests["http"]
    if "https" in _proxies_for_requests:
        os.environ["https_proxy"] = _proxies_for_requests["https"]

    worker_thread = threading.Thread(target=workflow_worker, args=(task_queue,), daemon=True)
    worker_thread.start()

    static_file_server_thread = threading.Thread(target=static_file_server.start, daemon=True)
    static_file_server_thread.start()

    background_task_server = BackgroundTaskServer(num_workers=2)
    background_task_server.start()

    ws_server = WebSocketServer(host="localhost", port=8765)
    ws_server.start()

    log_server = LogServer()
    log_server.start()

    register_shortcuts()

    if DEBUG:
        url = os.environ.get("VITE_LOCAL", "web/index.html")
    else:
        url = "web/index.html"
    webview.settings["ALLOW_DOWNLOADS"] = True
    window = webview.create_window(
        f"VectorVein v{VERSION}",
        url=url,
        js_api=api,
        width=config.get("window.width", 1600),
        height=config.get("window.height", 1000),
        x=config.get("window.x", 0),
        y=config.get("window.y", 0),
        on_top=config.get("window.on_top", False),
        confirm_close=True,
    )

    def on_close():
        config.close()
        background_task_server.stop()
        shortcuts_listener.stop()
        ws_server.stop()
        log_server.stop()
        window.destroy()

    def on_drop(e):
        """
        We need pywebviewFullPath to get the file path.
        So store the full path in cache and get them using get_drop_file_path in frontend.
        """
        files = e["dataTransfer"]["files"]
        if len(files) == 0:
            return e

        for file in files:
            cache.set(f"drop_file_{file.get('name')}", file.get("pywebviewFullPath"), expire=60)

        return e

    def on_moved(x, y):
        config.save("window.x", x)
        config.save("window.y", y)

    def on_resized(width, height):
        config.save("window.width", width)
        config.save("window.height", height)

    def bind(window):
        window.dom.document.events.drop += DOMEventHandler(on_drop)
        window.events.closed += on_close
        window.events.resized += on_resized
        window.events.moved += on_moved

    mprint(f"Debug: {DEBUG}")
    mprint(f"Version: {VERSION}")

    webview.start(bind, window, debug=DEBUG, http_server=True)


if __name__ == "__main__":
    main()
