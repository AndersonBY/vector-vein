# @Author: Bi Ying
# @Date:   2024-06-06 02:09:59
# config.py
import json
from pathlib import Path
from threading import Lock


class Config:
    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(Config, cls).__new__(cls, *args, **kwargs)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.default_config = {"data_path": "./data"}
        self.config_path = Path("./config.json")
        if not self.config_path.is_file():
            with open(self.config_path, "w", encoding="utf8") as config_file:
                json.dump(self.default_config, config_file)

        with open(self.config_path, "r") as config_file:
            self.config = json.load(config_file)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def save(self, key, value):
        self.config[key] = value
        with open(self.config_path, "w", encoding="utf8") as config_file:
            json.dump(self.config, config_file, indent=4, ensure_ascii=False)

    def update(self, key, value):
        self.config[key] = value
        with open(self.config_path, "w", encoding="utf8") as config_file:
            json.dump(self.config, config_file, indent=4, ensure_ascii=False)

    @property
    def data_path(self):
        return self.get("data_path", "./data")


config = Config()
