"""Managed knowledge bases. Metadata validation never starts the index owner."""
from __future__ import annotations

import threading
from pathlib import Path

from .service import KnowledgeService
from .storage import KnowledgeError, selected_metadata

__all__ = ["KnowledgeService", "KnowledgeError", "knowledge_service", "stop_knowledge_service", "selected_bases"]

_singleton = None
_singleton_lock = threading.Lock()


def _root():
    from utilities.config import config

    return Path(config.data_path) / "knowledge-base"


def knowledge_service() -> KnowledgeService:
    global _singleton
    with _singleton_lock:
        if _singleton is None or _singleton._closed:
            root = _root()
            _singleton = KnowledgeService(root, legacy_path=root.parent / "my_database.db")
        return _singleton


def stop_knowledge_service():
    with _singleton_lock:
        if _singleton is not None:
            _singleton.close()


def selected_bases(ids):
    """Read SQLite metadata only: no singleton, migrations, jobs, or vector handles."""
    return selected_metadata(_root(), ids)
