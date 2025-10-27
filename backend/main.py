# @Author: Bi Ying
# @Date:   2025-08-04
# Integrated FastAPI + PyWebView main application

import os
from pathlib import Path

import webview
from webview.window import Window
from webview.dom import DOMEventHandler

# Set up environment
os.environ["TIKTOKEN_CACHE_DIR"] = (Path(__file__).parent / Path("./assets/tiktoken_cache")).absolute().as_posix()

# Import existing components
from utilities.config import config, cache
from utilities.general import LogServer, mprint
from utilities.shortcuts import shortcuts_listener
from utilities.network import proxies_for_requests
from utilities.file_processing import static_file_server
from models import create_tables, run_migrations
from tts_server.server import tts_server
from chat_server.server import WebSocketServer

# Import new server components
from fastapi_server import FastAPIServer
from celery_worker import CeleryWorkerManager


class MainServer:
    def __init__(self):
        # Initialize debug and version info
        if Path("./DEBUG").exists():
            self.DEBUG = Path("./DEBUG").read_text() == "1"
        else:
            self.DEBUG = os.environ.get("VECTORVEIN_DEBUG", "0") == "1"
        if Path("./version.txt").exists():
            VERSION = Path("./version.txt").read_text()
        else:
            VERSION = os.environ.get("VECTORVEIN_VERSION", "0.0.1")

        # Create data directories
        data_path = Path(config.data_path)
        if not data_path.exists():
            data_path.mkdir()
            (data_path / "static").mkdir()
            (data_path / "static" / "images").mkdir()

        # Initialize database
        run_migrations()
        create_tables()

        mprint(f"TIKTOKEN_CACHE_DIR: {os.environ['TIKTOKEN_CACHE_DIR']}")
        mprint(f"Debug: {self.DEBUG}")
        mprint(f"Version: {VERSION}")

        # Set up proxy configuration
        _proxies_for_requests = proxies_for_requests()
        mprint("Proxies", _proxies_for_requests)

        if "http" in _proxies_for_requests:
            os.environ["http_proxy"] = _proxies_for_requests["http"]
        if "https" in _proxies_for_requests:
            os.environ["https_proxy"] = _proxies_for_requests["https"]

        # Start existing services first
        self.static_file_server = static_file_server
        self.static_file_server.start()

        # Start Celery worker using new manager
        self.celery_worker_manager = CeleryWorkerManager(concurrency=2)
        self.celery_worker_manager.start()

        self.ws_server = WebSocketServer(host="localhost", start_port=8765)
        self.ws_server.start()
        cache.set("chat_ws_port", self.ws_server.port)

        self.log_server = LogServer()
        self.log_server.start()

        self.tts_server = tts_server
        tts_server.start()

        self.shortcuts_listener = shortcuts_listener
        # Register shortcuts
        from api.user_api import register_shortcuts

        register_shortcuts()

        # Create API bridge for PyWebView
        from api_bridge import API

        api = API(self.DEBUG, VERSION)

        # Add all API classes like original main.py
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
            LogAPI,
            SettingAPI,
            HardwareAPI,
            ShortcutAPI,
        )
        from api.remote_api import OfficialSiteAPI

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
            LogAPI,
        ]

        mprint("Registering API classes...")
        for api_class in api_class_list:
            api.add_apis(api_class)

        # Add additional API methods like original main.py
        # Ensure these methods are available to JS before the window is created.
        API.get_drop_file_path = staticmethod(api.get_drop_file_path)

        # Expose native file/folder dialogs to JS early, using the active window when invoked.
        def _open_file_dialog(self, multiple=False):
            try:
                wnd = webview.windows[0] if webview.windows else None
            except Exception:
                wnd = None
            if wnd:
                result = wnd.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=multiple)
                if result:
                    return result if multiple else result[0]
            return [] if multiple else ""

        def _open_folder_dialog(self, initial_directory=""):
            try:
                wnd = webview.windows[0] if webview.windows else None
            except Exception:
                wnd = None
            if wnd:
                result = wnd.create_file_dialog(webview.FileDialog.FOLDER, directory=initial_directory)
                if result:
                    return result[0]
            return ""

        # # Register as instance methods (not static) so pywebview detects them
        API.open_file_dialog = _open_file_dialog  # type: ignore
        API.open_folder_dialog = _open_folder_dialog  # type: ignore

        # Debug: Print all registered methods
        if self.DEBUG:
            all_api_methods = [attr for attr in dir(API) if "__" in attr and not attr.startswith("_")]
            mprint(f"Total API methods registered (namespaced): {len(all_api_methods)}")
            mprint("First 10 namespaced methods:", all_api_methods[:10])
            # Verify open_file_dialog exposure on the api instance
            has_ofd = hasattr(api, "open_file_dialog")
            has_ofldr = hasattr(api, "open_folder_dialog")
            ofd_type = type(getattr(api, "open_file_dialog", None)).__name__
            ofldr_type = type(getattr(api, "open_folder_dialog", None)).__name__
            # List callable public methods on instance for sanity check
            public_callables = [name for name in dir(api) if not name.startswith("_") and callable(getattr(api, name))]
            mprint(f"open_file_dialog present: {has_ofd} ({ofd_type}), open_folder_dialog present: {has_ofldr} ({ofldr_type})")
            mprint(f"First 15 public callables on api instance: {public_callables[:15]}")

        mprint("API registration complete")

        # Store the api instance for later use
        self.api = api

        # Start FastAPI server using configured port or default
        api_host = config.get("api.host", "127.0.0.1")
        api_port = config.get("api.port", 8787)  # Default port 8787

        # Try to use configured port first
        try:
            self.api_server = FastAPIServer(host=api_host, port=api_port)
            self.api_server.start()
        except Exception as e:
            mprint(f"Failed to start on configured port {api_port}: {e}")
            # Fallback to auto-assign port
            mprint("Falling back to auto-assigned port...")
            self.api_server = FastAPIServer(host=api_host, port=0)
            self.api_server.start()
            # Save the auto-assigned port back to config for next time
            if self.api_server.actual_port:
                config.save("api.port", self.api_server.actual_port)

        # Save API server info to cache for external access
        cache.set("api_server_host", self.api_server.host)
        cache.set("api_server_port", self.api_server.actual_port)
        cache.set("api_server_url", f"http://{self.api_server.host}:{self.api_server.actual_port}")

        # Configure WebView URL - use FastAPI server to serve frontend
        if self.DEBUG:
            # In debug mode, check for Vite dev server first
            vite_url = os.environ.get("VITE_LOCAL")
            if vite_url and vite_url.startswith("http"):
                # Check if Vite dev server is actually running
                import httpx

                try:
                    response = httpx.get(vite_url, timeout=1)
                    if response.status_code == 200:
                        url = vite_url
                        mprint("Using Vite dev server for frontend")
                    else:
                        url = f"http://{self.api_server.host}:{self.api_server.actual_port}"
                        mprint("Vite dev server not responding, using FastAPI server for frontend")
                except Exception:
                    url = f"http://{self.api_server.host}:{self.api_server.actual_port}"
                    mprint("Vite dev server not available, using FastAPI server for frontend")
            else:
                url = f"http://{self.api_server.host}:{self.api_server.actual_port}"
                mprint("Using FastAPI server for frontend")
        else:
            url = f"http://{self.api_server.host}:{self.api_server.actual_port}"
            mprint("Using FastAPI server for frontend")

        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True

        # Create WebView window with js_api support
        self.window = webview.create_window(
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

    def terminate(self):
        """Terminate all services"""
        mprint("Terminating...")

        # Stop FastAPI server
        self.api_server.stop()

        # Stop Celery worker manager
        if hasattr(self, "celery_worker_manager"):
            self.celery_worker_manager.stop()

        # Stop other services
        config.close()
        self.static_file_server.shutdown()
        self.shortcuts_listener.stop()
        self.ws_server.stop()
        self.log_server.stop()
        self.tts_server.terminate()
        if self.window:
            self.window.destroy()

        mprint("Terminated.")

    @staticmethod
    def on_drop(e):
        """Handle file drop events"""
        files = e["dataTransfer"]["files"]
        if len(files) == 0:
            return e

        for file in files:
            cache.set(f"drop_file_{file.get('name')}", file.get("pywebviewFullPath"), expire=60)

        return e

    @staticmethod
    def on_moved(x, y):
        """Handle window move events"""
        config.save("window.x", x)
        config.save("window.y", y)

    @staticmethod
    def on_resized(width, height):
        """Handle window resize events"""
        config.save("window.width", width)
        config.save("window.height", height)

    def bind(self, window: Window):
        """Bind event handlers to window"""
        window.dom.document.events.drop += DOMEventHandler(MainServer.on_drop)  # type: ignore
        window.events.closed += self.terminate
        window.events.resized += MainServer.on_resized
        window.events.moved += MainServer.on_moved

    def start(self):
        """Start the application"""
        webview.start(self.bind, [self.window], debug=self.DEBUG, http_server=False)


if __name__ == "__main__":
    main_server = MainServer()
    main_server.start()
