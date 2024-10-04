# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 01:26:36
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-17 15:58:03
import time
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from threading import Thread, Event

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

    def warning(self, *args):
        try:
            self.queue.append(("warning", " ".join([str(arg) for arg in args])))
        except Exception:
            pass

    def error(self, *args):
        try:
            self.queue.append(("error", " ".join([str(arg) for arg in args])))
        except Exception:
            pass


class LogServer:
    _instances: dict[str, "LogServer"] = {}

    def __init__(self, log_path: Path | None = None):
        if log_path is None:
            _log_path = Path(Settings().get("log_path", "./log"))

            if not _log_path.exists():
                _log_path.mkdir()

            log_file = _log_path / "vector-vein.log"
            if log_file.exists() and log_file.stat().st_size / 1024 / 1024 > 10:
                dt_now_str = datetime.now().strftime("%Y-%m-%d")
                log_file.rename(_log_path / f"vector-vein.log.{dt_now_str}")
        else:
            _log_path = log_path

        self.log_path = _log_path
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

        self.log_id = str(log_path) if log_path else "default"
        LogServer._instances[self.log_id] = self

        self.stop_event = Event()

    def log_listener(self):
        while not self.stop_event.is_set():
            if len(self.log_queue) > 0:
                pop_result = self.log_queue.popleft()
                if pop_result is None:
                    continue
                level, message = pop_result
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
        self.stop_event.set()
        self.listener_thread.join(timeout=5)

    @classmethod
    def get(cls, log_id: str) -> "LogServer | None":
        """
        通过 log_id 获取对应的 LogServer 实例
        Get the corresponding LogServer instance by log_id
        """
        return cls._instances.get(log_id)

    def get_log_content(self, tail: int = 1000):
        """
        获取当前日志文件的内容
        Get the content of the current log file
        """
        log_file = self.log_path / "vector-vein.log"
        if log_file.exists():
            with open(log_file, "rb") as f:
                f.seek(0, 2)
                file_size = f.tell()
                lines = []
                bytes_read = 0
                while len(lines) < tail and bytes_read < file_size:
                    bytes_to_read = min(1024, file_size - bytes_read)
                    f.seek(-bytes_to_read - bytes_read, 2)
                    chunk = f.read(bytes_to_read)
                    lines.extend(chunk.decode("utf-8", errors="ignore").splitlines())
                    bytes_read += bytes_to_read
                return lines[-tail:][::-1]
        else:
            mprint.error(f"Log file does not exist: {log_file}")
            return []

    @classmethod
    def get_log_content_by_id(cls, log_id: str, tail: int = 1000) -> list[str]:
        """
        通过 log_id 获取对应的日志内容
        Get the content of the log file by log_id
        """
        instance = cls.get(log_id)
        if instance:
            return instance.get_log_content(tail)
        else:
            mprint.error(f"No log server instance found with ID {log_id}")
            return []


log_queue = Deque(directory=Path(config.data_path) / "cache" / "log_queue")

mprint = MPrint(log_queue)
