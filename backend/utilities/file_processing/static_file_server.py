# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-17 20:17:51
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-08-07 19:32:57
import uuid
import shutil
import hashlib
from pathlib import Path
from urllib.parse import unquote, urlparse
from http.server import SimpleHTTPRequestHandler, HTTPServer

import httpx

from utilities.config import config
from utilities.general import mprint


class StaticFileServer:
    host = "localhost"
    port = 13286

    def __init__(self, static_folder_path: str | Path):
        class MyRequestHandler(SimpleHTTPRequestHandler):
            def end_headers(self):
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET")
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                return super(MyRequestHandler, self).end_headers()

            def translate_path(self, path):
                path = unquote(path.split("?", 1)[0].split("#", 1)[0])
                file_path = str(Path(static_folder_path, path.strip("/")))
                return file_path

            def do_GET(self):
                self.path = unquote(self.path)
                super().do_GET()

        self.static_folder_path = Path(static_folder_path)
        self.static_file_server = HTTPServer((StaticFileServer.host, StaticFileServer.port), MyRequestHandler)

    @staticmethod
    def get_file_url(file_path):
        return f"http://{StaticFileServer.host}:{StaticFileServer.port}/{file_path}"

    def start(self):
        mprint(f"Starting static file server at http://{StaticFileServer.host}:{StaticFileServer.port}")
        self.static_file_server.serve_forever()

    def shutdown(self):
        mprint("Shutting down static file server")
        self.static_file_server.shutdown()

    def restart(self):
        self.shutdown()
        self.start()

    @staticmethod
    def copy_file(src, dst):
        if Path(src).exists():
            if dst.exists():
                dst = dst.with_name(f"{uuid.uuid4().hex}_{dst.name}")
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dst)
            return dst
        return None

    @staticmethod
    def copy_online_file(file_url: str, folder: str | Path):
        response = httpx.get(file_url, timeout=30)
        if response.status_code == 200:
            file_type = response.headers.get("Content-Type", "").split("/")[-1]
            file_name = urlparse(file_url).path.split("/")[-1]
            if len(file_name) == 0:
                file_name = uuid.uuid4().hex
            if isinstance(folder, str):
                folder = Path(folder)
            original_file = dst = folder / file_name
            if dst.exists():
                dst = dst.with_name(f"{uuid.uuid4().hex}_{dst.name}")
            else:
                dst = dst.with_suffix(f".{file_type}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            with open(dst, "wb") as f:
                f.write(response.content)

            if all(
                (
                    original_file.exists(),
                    StaticFileServer.calculate_md5(original_file) == StaticFileServer.calculate_md5(dst),
                    original_file.absolute() != dst.absolute(),
                )
            ):
                dst.unlink()
                return original_file
            return dst

    @staticmethod
    def calculate_md5(file_path: str | Path):
        if not Path(file_path).exists():
            return None
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()

    def find_file_in_static_dir(self, local_file_path, static_subdir):
        local_file_md5 = self.calculate_md5(local_file_path)
        static_dir_path: Path = self.static_folder_path / static_subdir

        if not static_dir_path.exists():
            return None

        for file in static_dir_path.iterdir():
            if file.is_file():
                if self.calculate_md5(file) == local_file_md5:
                    return file.relative_to(self.static_folder_path).as_posix()

        return None

    def get_static_file_url(self, file: str | Path, static_subdir: str | Path):
        """
        Get the URL of a file on the static file server. If the file does not exist in the static directory,
        it will be copied there.

        Parameters:
        local_file_path (str | Path): The path/url to the file.
        static_subdir (str | Path): The subdirectory on the static file server.

        Returns:
        str: The URL of the static file. If the file copy fails, returns None.
        """
        if isinstance(file, str) and file.startswith("http"):
            file_path = self.copy_online_file(file, self.static_folder_path / static_subdir)
            if file_path:
                return self.get_file_url(file_path.relative_to(self.static_folder_path).as_posix())
            else:
                return None

        found_file = self.find_file_in_static_dir(file, static_subdir)
        if found_file:
            return self.get_file_url(found_file)
        else:
            dst_path = self.static_folder_path / static_subdir / Path(file).name
            if self.copy_file(file, dst_path):
                return self.get_file_url(dst_path.relative_to(self.static_folder_path).as_posix())
            else:
                return None


static_file_server = StaticFileServer(Path(config.data_path) / "static")
