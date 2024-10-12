# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 01:29:11
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-07-01 18:18:40
import os
import uuid
import base64
import subprocess
from io import BytesIO
from pathlib import Path

from PIL import Image

from utilities.config import config
from utilities.general import mprint_with_name


mprint = mprint_with_name(name="API")


class API:
    def __init__(self, debug=False, version=None):
        self.debug = debug
        self.version = version

    def add_apis(self, APIClass):
        for method_name in dir(APIClass):
            method = getattr(APIClass, method_name)
            if callable(method) and not method_name.startswith("_"):
                setattr(API, f"{APIClass.name}__{method_name}", method)

    def open_local_file(self, file):
        try:
            if os.name == "nt":
                os.startfile(file)
            else:
                subprocess.Popen(["open", file])
            return True
        except Exception as e:
            mprint.error(e)
            return False

    def get_local_file_base64(self, file):
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
            mprint.error(e)
            return None

    def save_image(self, image_base64):
        image_path = Path(config.data_path) / "images" / f"{uuid.uuid4().hex}.png"

        header, base64_data = image_base64.split(",", 1)

        image_data = base64.b64decode(base64_data)

        image = Image.open(BytesIO(image_data))
        image.save(image_path)

        return str(image_path.resolve())
