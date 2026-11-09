# @Author: Bi Ying
# @Date:   2024-06-09 11:47:37
from utilities.upgrade_backup import ensure_workspace_v1_upgrade_backup

# Imports below may normalize persisted settings or create cache files.
ensure_workspace_v1_upgrade_backup()

from .config import config  # noqa: E402
from .cache import cache  # noqa: E402
from .settings import Settings, DEFAULT_SETTINGS  # noqa: E402


__all__ = [
    "cache",
    "config",
    "Settings",
    "DEFAULT_SETTINGS",
]
