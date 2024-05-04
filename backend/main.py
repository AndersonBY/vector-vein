# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-14 23:56:32
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-05-04 12:34:12
import os
import queue
import threading
from pathlib import Path

import webview
import mimetypes

from api import API
from api.workflow_api import (
    WorkflowAPI,
    WorkflowTagAPI,
    WorkflowTemplateAPI,
    WorkflowRunRecordAPI,
    WorkflowRunScheduleAPI,
)
from api.database_api import DatabaseAPI, DatabaseObjectAPI
from api.relational_database_api import (
    RelationalDatabaseAPI,
    RelationalDatabaseTableAPI,
    RelationalDatabaseTableRecordAPI,
)
from api.user_api import SettingAPI
from api.remote_api import OfficialSiteAPI
from utilities.print_utils import mprint
from utilities.web_crawler import proxies_for_requests
from utilities.static_file_server import StaticFileServer
from models import create_tables
from worker import main_worker, main_vector_database


# Some mimetypes are not correctly registered in Windows. Register them manually.
mimetypes.add_type("application/javascript", ".js")

if not Path("./data").exists():
    Path("./data").mkdir()
    Path("./data/static").mkdir()
    Path("./data/static/images").mkdir()

# Create SQLite tables. Will ignore if tables already exist.
create_tables()


def open_file_dialog(self, multiple=False):
    result = window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=multiple)
    return result


def open_folder_dialog(self, initial_directory=""):
    result = window.create_file_dialog(webview.FOLDER_DIALOG, directory=initial_directory)
    return result


if Path("./DEBUG").exists():
    DEBUG = Path("./DEBUG").read_text() == "1"
else:
    DEBUG = os.environ.get("VECTORVEIN_DEBUG", "0") == "1"

if Path("./version.txt").exists():
    VERSION = Path("./version.txt").read_text()
else:
    VERSION = os.environ.get("VECTORVEIN_VERSION", "0.0.1")

mprint(f"Debug: {DEBUG}")
mprint(f"Version: {VERSION}")

task_queue = queue.Queue()
vdb_queues = {
    "request": queue.Queue(),
    "response": queue.Queue(),
}
api = API(DEBUG, VERSION, task_queue, vdb_queues)
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
]
for api_class in api_class_list:
    api.add_apis(api_class)
setattr(API, "open_file_dialog", open_file_dialog)
setattr(API, "open_folder_dialog", open_folder_dialog)

_proxies_for_requests = proxies_for_requests()

if "http" in _proxies_for_requests:
    os.environ["http_proxy"] = _proxies_for_requests["http"]
if "https" in _proxies_for_requests:
    os.environ["https_proxy"] = _proxies_for_requests["https"]

worker_thread = threading.Thread(target=main_worker, args=(task_queue, vdb_queues), daemon=True)
worker_thread.start()

vdb_thread = threading.Thread(target=main_vector_database, args=(vdb_queues,), daemon=True)
vdb_thread.start()

static_file_server = StaticFileServer("./data/static")
static_file_server_thread = threading.Thread(target=static_file_server.start, daemon=True)
static_file_server_thread.start()

if DEBUG:
    url = os.environ.get("VITE_LOCAL", "web/index.html")
else:
    url = "web/index.html"
webview.settings["ALLOW_DOWNLOADS"] = True
window = webview.create_window(
    f"VectorVein v{VERSION}",
    url=url,
    js_api=api,
    width=1600,
    height=1000,
    confirm_close=True,
)
webview.start(debug=DEBUG, http_server=True)
