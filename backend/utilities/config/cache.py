# @Author: Bi Ying
# @Date:   2024-06-07 13:31:52
from pathlib import Path

from diskcache import Cache

from .config import config

cache = Cache(Path(config.data_path) / "cache")
