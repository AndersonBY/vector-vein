# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-17 20:17:51
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-17 20:40:18
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, HTTPServer


class StaticFileServer:
    host = "localhost"
    port = 13286

    def __init__(self, static_folder_path):
        class MyRequestHandler(SimpleHTTPRequestHandler):
            def translate_path(self, path):
                path = path.split("?", 1)[0]
                path = path.split("#", 1)[0]
                file_path = str(Path(static_folder_path, path.strip("/")))
                return file_path

        self.static_file_server = HTTPServer((StaticFileServer.host, StaticFileServer.port), MyRequestHandler)

    @staticmethod
    def get_file_url(file_path):
        return f"http://{StaticFileServer.host}:{StaticFileServer.port}/{file_path}"

    def start(self):
        self.static_file_server.serve_forever()

    def shutdown(self):
        self.static_file_server.shutdown()

    def restart(self):
        self.shutdown()
        self.start()
