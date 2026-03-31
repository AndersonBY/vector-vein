from __future__ import annotations

import os
import sys
from pathlib import Path


TIKTOKEN_CACHE_DIR = (Path(__file__).parent / "assets" / "tiktoken_cache").absolute()
os.environ["TIKTOKEN_CACHE_DIR"] = TIKTOKEN_CACHE_DIR.as_posix()

APP_ROOT = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
