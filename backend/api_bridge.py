# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2025-08-04
# API compatibility layer for PyWebView integration

import os
import time
import base64
import subprocess
from io import BytesIO
from pathlib import Path

from PIL import Image

from utilities.config import config, cache
from utilities.general import mprint_with_name

# Import all existing API classes
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

mprint = mprint_with_name(name="API Compatibility")


class APIBridge:
    """
    Bridge class that provides the same API interface as the original API class
    but can work with both PyWebView and standalone FastAPI calls
    """

    def __init__(self, debug=False, version=None):
        self.debug = debug
        self.version = version

        # Initialize all API classes
        self.api_classes = {}
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

        for api_class in api_class_list:
            # Create instance of the API class
            api_instance = api_class()
            self.api_classes[api_class.name] = api_instance

            # Add API methods as instance methods
            for method_name in dir(api_instance):
                method = getattr(api_instance, method_name)
                if callable(method) and not method_name.startswith("_") and hasattr(api_instance.__class__, method_name):
                    # Bind the method to this APIBridge instance
                    setattr(self, f"{api_class.name}__{method_name}", method)

    def open_file_dialog(self, multiple=False):
        """Open file dialog - stub implementation"""
        # In web context, this would need to be handled differently
        return [] if multiple else ""

    def open_folder_dialog(self, initial_directory=""):
        """Open folder dialog - stub implementation"""
        # In web context, this would need to be handled differently
        return ""

    def get_drop_file_path(self, file_name):
        """Get dropped file path from cache"""
        start_time = time.time()
        while time.time() - start_time < 5:
            file_paths = cache.get(f"drop_file_{file_name}")
            if file_paths:
                cache.delete(f"drop_file_{file_name}")
                return file_paths
            time.sleep(0.1)
        return []

    def open_local_file(self, file):
        """Open local file"""
        try:
            if os.name == "nt":
                os.startfile(file)
            else:
                subprocess.Popen(["open", file])
            return True
        except Exception as e:
            mprint.error(f"Failed to open file {file}: {e}")
            return False

    def get_local_file_base64(self, file):
        """Get local file as base64"""
        try:
            with open(file, "rb") as f:
                data = f.read()
                if file.endswith(".png"):
                    return f"data:image/png;base64,{base64.b64encode(data).decode()}"
                elif file.endswith(".jpg") or file.endswith(".jpeg"):
                    return f"data:image/jpeg;base64,{base64.b64encode(data).decode()}"
                elif file.endswith(".gif"):
                    return f"data:image/gif;base64,{base64.b64encode(data).decode()}"
                else:
                    return base64.b64encode(data).decode()
        except Exception as e:
            mprint.error(f"Failed to read file {file}: {e}")
            return None

    def save_image(self, image_base64):
        """Save image from base64"""
        try:
            image_path = Path(config.data_path) / "images" / f"{time.time():.0f}.png"

            header, base64_data = image_base64.split(",", 1)
            image_data = base64.b64decode(base64_data)

            image = Image.open(BytesIO(image_data))
            image.save(image_path)

            return str(image_path.resolve())
        except Exception as e:
            mprint.error(f"Failed to save image: {e}")
            return None


# Create a global API bridge instance
api_bridge = APIBridge()


# For backward compatibility, create an API class that behaves like the original
class API:
    def __init__(self, debug=False, version=None):
        self.debug = debug
        self.version = version
        mprint(f"API initialized with debug={debug}, version={version}")

    def add_apis(self, APIClass):
        """Add APIs - matches original API behavior by adding to class itself"""
        mprint(f"Adding API class: {APIClass.__name__} (name: {APIClass.name})")

        # Create instance of the API class for method calls
        api_instance = APIClass()

        # Add methods to the API class itself (not instance) - this matches original behavior
        method_count = 0
        for method_name in dir(api_instance):
            method = getattr(api_instance, method_name)
            if callable(method) and not method_name.startswith("_") and hasattr(api_instance.__class__, method_name):
                # Create a bound method name like the original
                bound_method_name = f"{APIClass.name}__{method_name}"
                setattr(API, bound_method_name, method)
                method_count += 1
                if self.debug:
                    mprint(f"  Added method: {bound_method_name}")

        mprint(f"Added {method_count} methods from {APIClass.__name__}")

    @staticmethod
    def open_file_dialog(multiple=False):
        """Open file dialog - stub implementation"""
        mprint(f"open_file_dialog called with multiple={multiple}")
        # In web context, this would need to be handled differently
        return [] if multiple else ""

    @staticmethod
    def open_folder_dialog(initial_directory=""):
        """Open folder dialog - stub implementation"""
        mprint(f"open_folder_dialog called with initial_directory={initial_directory}")
        # In web context, this would need to be handled differently
        return ""

    @staticmethod
    def get_drop_file_path(file_name):
        """Get dropped file path from cache"""
        mprint(f"get_drop_file_path called with file_name={file_name}")
        start_time = time.time()
        while time.time() - start_time < 5:
            file_paths = cache.get(f"drop_file_{file_name}")
            if file_paths:
                cache.delete(f"drop_file_{file_name}")
                return file_paths
            time.sleep(0.1)
        return []

    @staticmethod
    def open_local_file(file):
        """Open local file"""
        mprint(f"open_local_file called with file={file}")
        try:
            if os.name == "nt":
                os.startfile(file)
            else:
                subprocess.Popen(["open", file])
            return True
        except Exception as e:
            mprint.error(f"Failed to open file {file}: {e}")
            return False

    @staticmethod
    def get_local_file_base64(file):
        """Get local file as base64"""
        mprint(f"get_local_file_base64 called with file={file}")
        try:
            with open(file, "rb") as f:
                data = f.read()
                if file.endswith(".png"):
                    return f"data:image/png;base64,{base64.b64encode(data).decode()}"
                elif file.endswith(".jpg") or file.endswith(".jpeg"):
                    return f"data:image/jpeg;base64,{base64.b64encode(data).decode()}"
                elif file.endswith(".gif"):
                    return f"data:image/gif;base64,{base64.b64encode(data).decode()}"
                else:
                    return base64.b64encode(data).decode()
        except Exception as e:
            mprint.error(f"Failed to read file {file}: {e}")
            return None

    @staticmethod
    def debug_api_call(method_name, *args, **kwargs):
        """Debug wrapper for API calls"""
        mprint(f"🔍 API Call: {method_name} with args={args}, kwargs={kwargs}")
        try:
            if hasattr(API, method_name):
                method = getattr(API, method_name)
                result = method(*args, **kwargs)
                mprint(f"✅ API Call Success: {method_name} -> {type(result)}")
                return result
            else:
                mprint(f"❌ API Method Not Found: {method_name}")
                raise AttributeError(f"API has no attribute '{method_name}'")
        except Exception as e:
            mprint(f"💥 API Call Failed: {method_name} -> {type(e).__name__}: {e}")
            raise

    @staticmethod
    def save_image(image_base64):
        """Save image from base64"""
        mprint("save_image called")
        try:
            image_path = Path(config.data_path) / "images" / f"{time.time():.0f}.png"
            image_path.parent.mkdir(parents=True, exist_ok=True)

            header, base64_data = image_base64.split(",", 1)
            image_data = base64.b64decode(base64_data)

            image = Image.open(BytesIO(image_data))
            image.save(image_path)

            return str(image_path.resolve())
        except Exception as e:
            mprint.error(f"Failed to save image: {e}")
            return None

    def __getattr__(self, name):
        """Delegate attribute access to class methods"""
        mprint(f"API.__getattr__ called for: {name}")
        if hasattr(API, name):
            method = getattr(API, name)
            mprint(f"Found method: {name} -> {type(method)}")
            return method

        # More detailed debugging
        mprint(f"Method not found: {name}")

        # Show available methods with similar names
        all_methods = [attr for attr in dir(API) if not attr.startswith("_")]
        similar_methods = [m for m in all_methods if name.split("__")[0] in m or name.split("__")[-1] in m]
        if similar_methods:
            mprint(f"Similar methods available: {similar_methods[:5]}")

        # Show all methods starting with the same prefix
        if "__" in name:
            prefix = name.split("__")[0]
            prefix_methods = [m for m in all_methods if m.startswith(prefix + "__")]
            if prefix_methods:
                mprint(f"Methods with prefix '{prefix}__': {prefix_methods}")

        raise AttributeError(f"API has no attribute '{name}'")
