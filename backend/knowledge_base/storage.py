"""Managed knowledge metadata. Importing this module never opens application data."""
from __future__ import annotations

import os
import re
import sqlite3
import stat
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID


class KnowledgeError(ValueError):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.status = code, status


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def identifier(value) -> str:
    try:
        if not isinstance(value, str) or UUID(value).hex != value:
            raise ValueError
        return value
    except (ValueError, AttributeError):
        raise KnowledgeError("invalid_id", "A valid knowledge base or item ID is required.") from None


def name_value(value) -> str:
    if (not isinstance(value, str) or not value.strip() or len(value) > 240
            or value.strip() in {".", ".."} or re.search(r'[<>:"/\\|?*\x00-\x1f]', value)
            or value.endswith((" ", "."))):
        raise KnowledgeError("invalid_name", "Use a name of 1–240 characters without path separators.")
    return value.strip()


def safe_path(path: Path, *, exists: bool = True) -> Path:
    """Reject links and Windows junction/reparse components, including ancestors."""
    path = Path(os.path.abspath(path))
    for component in (*reversed(path.parents), path):
        try:
            info = component.lstat()
        except FileNotFoundError:
            if component == path and exists:
                raise KnowledgeError("file_missing", "The file is no longer available.") from None
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise KnowledgeError("unsafe_path", "Symbolic links and junctions cannot be imported.")
    return path


def acquire_owner(root: Path):
    """Hold one persistent lock inode; never unlink or truncate a live lock file."""
    import portalocker

    safe_path(root, exists=False)
    root.mkdir(parents=True, exist_ok=True)
    path = safe_path(root / ".owner.lock", exists=False)
    owner = path.open("a+b")
    try:
        current = safe_path(path).stat()
        opened = os.fstat(owner.fileno())
        if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
            raise KnowledgeError("unsafe_path", "The knowledge storage owner lock changed.")
        portalocker.lock(owner, portalocker.LockFlags.EXCLUSIVE | portalocker.LockFlags.NON_BLOCKING)
    except portalocker.exceptions.LockException:
        owner.close()
        raise KnowledgeError("owner_in_use", "Knowledge storage is already open in another desktop service.", 409) from None
    except BaseException:
        owner.close()
        raise
    return owner


def connect(root: Path) -> sqlite3.Connection:
    safe_path(root, exists=False)
    root.mkdir(parents=True, exist_ok=True)
    safe_path(root / "metadata.sqlite3", exists=False)
    db = sqlite3.connect(root / "metadata.sqlite3", check_same_thread=False, isolation_level=None, timeout=15)
    try:
        _initialize(db)
    except BaseException:
        db.close()
        raise
    return db


def _initialize(db):
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS bases (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
            embedding_provider TEXT NOT NULL, embedding_model TEXT NOT NULL,
            embedding_dimensions INTEGER, resolved_dimensions INTEGER,
            chunk_size INTEGER NOT NULL, chunk_overlap INTEGER NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY, kb_id TEXT NOT NULL REFERENCES bases(id) ON DELETE CASCADE,
            parent_id TEXT REFERENCES items(id) ON DELETE CASCADE,
            kind TEXT NOT NULL CHECK(kind IN ('file','folder')), name TEXT NOT NULL,
            status TEXT NOT NULL, byte_size INTEGER NOT NULL DEFAULT 0,
            original TEXT, source_url TEXT NOT NULL DEFAULT '', extracted_text TEXT NOT NULL DEFAULT '',
            generation INTEGER NOT NULL DEFAULT 0, active_token TEXT,
            chunk_count INTEGER NOT NULL DEFAULT 0, error_code TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS item_siblings ON items(kb_id, IFNULL(parent_id,''), name COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS item_parent ON items(kb_id,parent_id);
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            generation INTEGER NOT NULL, status TEXT NOT NULL, phase TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL DEFAULT 0,
            error_code TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS job_queue ON jobs(status,created_at);
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            token TEXT NOT NULL, chunk_index INTEGER NOT NULL, text TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS chunk_document ON chunks(document_id,token);
        CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
            chunk_id UNINDEXED, text, tokenize='trigram'
        );
        CREATE TRIGGER IF NOT EXISTS chunk_removed AFTER DELETE ON chunks BEGIN
            DELETE FROM chunk_fts WHERE chunk_id=old.id;
        END;
        CREATE TRIGGER IF NOT EXISTS chunk_added AFTER INSERT ON chunks BEGIN
            INSERT INTO chunk_fts(chunk_id,text) VALUES(new.id,new.text);
        END;
        CREATE TABLE IF NOT EXISTS legacy_imports (kind TEXT NOT NULL, id TEXT NOT NULL, PRIMARY KEY(kind,id));
    """)


def selected_metadata(root: Path, ids) -> list[dict]:
    if not isinstance(ids, list) or len(ids) > 20:
        raise KnowledgeError("invalid_scope", "Select at most 20 knowledge bases.")
    clean = [identifier(value) for value in ids]
    if len(set(clean)) != len(clean):
        raise KnowledgeError("duplicate_scope", "Knowledge base selections must be unique.")
    if not clean:
        return []
    try:
        path = safe_path(root / "metadata.sqlite3")
    except KnowledgeError as error:
        if error.code == "file_missing":
            raise KnowledgeError("not_found", "A selected knowledge base no longer exists.", 404) from None
        raise
    try:
        db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=15)
    except sqlite3.Error:
        raise KnowledgeError("metadata_unavailable", "Knowledge metadata is unavailable. Restart the desktop application.", 503) from None
    try:
        output = []
        for key in clean:
            row = db.execute("SELECT name FROM bases WHERE id=?", (key,)).fetchone()
            if row is None:
                raise KnowledgeError("not_found", "A selected knowledge base no longer exists.", 404)
            output.append({"kb_id": key, "name": row[0]})
        return output
    except sqlite3.Error:
        raise KnowledgeError("metadata_unavailable", "Knowledge metadata is unavailable. Restart the desktop application.", 503) from None
    finally:
        db.close()
