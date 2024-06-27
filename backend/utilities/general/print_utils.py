# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 01:26:36
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-17 15:58:03
import time
import logging
import logging.handlers
from pathlib import Path
from threading import Thread
from datetime import datetime

from diskcache import Deque

from utilities.config import config, Settings


class MPrint:
    def __init__(self, queue):
        self.queue = queue

    def __call__(self, *args):
        self.info(*args)

    def debug(self, *args):
        try:
            self.queue.append(("debug", " ".join([str(arg) for arg in args])))
        except Exception:
            pass

    def info(self, *args):
        try:
            self.queue.append(("info", " ".join([str(arg) for arg in args])))
        except Exception:
            pass

    def error(self, *args):
        try:
            self.queue.append(("error", " ".join([str(arg) for arg in args])))
        except Exception:
            pass


class LogServer:
    def __init__(self, log_path: Path | None = None):
        if log_path is None:
            log_path = Path(Settings().get("log_path", "./log"))

            if not log_path.exists():
                log_path.mkdir()

            log_file = log_path / "vector-vein.log"
            if log_file.exists() and log_file.stat().st_size / 1024 / 1024 > 10:
                dt_now_str = datetime.now().strftime("%Y-%m-%d")
                log_file.rename(log_path / f"vector-vein.log.{dt_now_str}")

        self.log_path = log_path
        self.log_queue = Deque(directory=Path(config.data_path) / "cache" / "log_queue")
        self.logger = logging.getLogger("vector-vein")
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(message)s")

        log_handler = logging.handlers.TimedRotatingFileHandler(
            self.log_path / "vector-vein.log",
            when="D",
            interval=1,
            backupCount=20,
            encoding="utf8",
        )
        log_handler.setLevel(logging.DEBUG)
        log_handler.setFormatter(formatter)

        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        console.setFormatter(formatter)
        console.stream = open(console.stream.fileno(), "w", encoding="utf-8", closefd=False)

        self.logger.addHandler(log_handler)
        self.logger.addHandler(console)

        self.listener_thread = Thread(target=self.log_listener)
        self.listener_thread.daemon = True

    def log_listener(self):
        while True:
            if len(self.log_queue) > 0:
                level, message = self.log_queue.popleft()
                if level == "debug":
                    self.logger.debug(message)
                elif level == "info":
                    self.logger.info(message)
                elif level == "error":
                    self.logger.error(message)
            else:
                time.sleep(0.1)

    def start(self):
        self.listener_thread.start()

    def stop(self):
        self.listener_thread.join()


log_queue = Deque(directory=Path(config.data_path) / "cache" / "log_queue")

mprint = MPrint(log_queue)
