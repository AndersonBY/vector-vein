# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 01:26:36
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-05 23:46:05
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime

from .settings import Settings


def mprint(*args):
    logger.info(" ".join([str(arg) for arg in args]))


def mprint_error(*args):
    logger.error(" ".join([str(arg) for arg in args]))


log_path = Path(Settings().get("log_path", "./log"))

if not log_path.exists():
    log_path.mkdir()

log_file = log_path / "vector-vein.log"
if log_file.exists() and log_file.stat().st_size / 1024 / 1024 > 10:
    dt_now_str = datetime.now().strftime("%Y-%m-%d")
    log_file.rename(log_path / f"vector-vein.log.{dt_now_str}")

logger = logging.getLogger("vector-vein")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(message)s")
log_handler = logging.handlers.TimedRotatingFileHandler(
    log_path / "vector-vein.log", when="D", interval=1, backupCount=20
)
log_handler.setLevel(logging.DEBUG)
log_handler.setFormatter(formatter)
logger.addHandler(log_handler)
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
console.setFormatter(formatter)
logger.addHandler(console)
