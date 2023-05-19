# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 01:29:11
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-17 19:55:15
import os
import subprocess

from utilities.print_utils import mprint_error


class API:
    def __init__(self, debug=False, version=None, worker_queue=None, vdb_queues=None):
        self.debug = debug
        self.version = version
        self.worker_queue = worker_queue
        self.vdb_queues = vdb_queues
        self.data_path = "./data"

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
            mprint_error(e)
            return False
