# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-15 01:26:36
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-15 11:21:39
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime


if not Path("./log").exists():
    Path("./log").mkdir()

log_file = Path("./log/vector-vein.log")
if log_file.exists() and log_file.stat().st_size / 1024 / 1024 > 10:
    dt_now_str = datetime.now().strftime("%Y-%m-%d")
    log_file.rename(f"./log/vector-vein.log.{dt_now_str}")

logger = logging.getLogger("vector-vein")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(message)s")
log_handler = logging.handlers.TimedRotatingFileHandler("./log/vector-vein.log", when="D", interval=1)
log_handler.setLevel(logging.DEBUG)
log_handler.setFormatter(formatter)
logger.addHandler(log_handler)
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
console.setFormatter(formatter)
logger.addHandler(console)


def mprint(*args):
    logger.info(" ".join([str(arg) for arg in args]))


def mprint_error(*args):
    logger.error(" ".join([str(arg) for arg in args]))
