"""Non-destructive, repeatable migration of legacy business records only."""
from __future__ import annotations

import json
import sqlite3
from uuid import UUID, uuid4

from .storage import now, safe_path
from .service import MAX_TEXT, chunks_for


def legacy_name(value, key):
    text = str(value or "").strip()
    text = "".join("_" if char in '<>:"/\\|?*' or ord(char) < 32 else char for char in text)
    return text[:200].rstrip(". ") or key


def migrate_legacy(service, path):
    if not path.is_file():
        return
    path = safe_path(path)
    source = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        tables = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"user_vector_database", "user_object"} <= tables:
            return
        # Read under one source snapshot, without changing or deleting legacy rows.
        source.execute("BEGIN")
        for row in source.execute("SELECT * FROM user_vector_database"):
            dataset = dict(row)
            try:
                kb_id = UUID(str(dataset["vid"])).hex
            except (ValueError, KeyError):
                continue
            with service._write():
                seen = service._db.execute("SELECT 1 FROM legacy_imports WHERE kind='base' AND id=?", (kb_id,)).fetchone()
                if seen is None:
                    stamp = now()
                    service._db.execute("""
                        INSERT OR IGNORE INTO bases VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    """, (kb_id, legacy_name(dataset.get("name"), kb_id), "",
                          str(dataset.get("embedding_provider") or "openai"),
                          str(dataset.get("embedding_model") or "text-embedding-ada-002"),
                          dataset.get("embedding_size") or 1536, dataset.get("embedding_size") or 1536,
                          1000, 150, stamp, stamp))
                    service._db.execute("INSERT INTO legacy_imports VALUES('base',?)", (kb_id,))
                if not service._db.execute("SELECT 1 FROM bases WHERE id=?", (kb_id,)).fetchone():
                    continue
            for object_row in source.execute("SELECT * FROM user_object WHERE vector_database_id=?", (dataset["id"],)):
                document = dict(object_row)
                try:
                    document_id = UUID(str(document["oid"])).hex
                except (ValueError, TypeError, KeyError):
                    continue
                try:
                    raw = json.loads(document.get("raw_data") or "{}")
                except (ValueError, TypeError):
                    raw = {}
                if not isinstance(raw, dict):
                    raw = {}
                text = raw.get("text")
                if not isinstance(text, str) or not text.strip():
                    segments = raw.get("segments")
                    text = "\n\n".join(str(segment.get("text", "")) for segment in segments if isinstance(segment, dict)) if isinstance(segments, list) else ""
                text = text[:MAX_TEXT]
                with service._write():
                    if service._db.execute("SELECT 1 FROM legacy_imports WHERE kind='document' AND id=?", (document_id,)).fetchone():
                        continue
                    name = legacy_name(document.get("title"), document_id)
                    if service._db.execute("SELECT 1 FROM items WHERE kb_id=? AND parent_id IS NULL AND name=? COLLATE NOCASE", (kb_id, name)).fetchone():
                        name += " " + document_id[:8]
                    physical = None
                    try:
                        # Only copy validated regular sources. Never follow legacy links or
                        # extract archives; recovered text is the safe fallback original.
                        candidate = raw.get("file")
                        if isinstance(candidate, str):
                            original = service._source(candidate)
                            # A fresh physical ID makes retry after an interrupted SQLite
                            # transaction safe without overwriting any previous original.
                            physical, _ = service._copy_original(original, uuid4().hex)
                    except (ValueError, OSError):
                        if physical is not None:
                            safe_path(service.originals / physical, exists=False).unlink(missing_ok=True)
                        physical = None
                    if physical is None:
                        physical = service._text_original(uuid4().hex, text)
                    service._insert_item(kb_id, None, name, "file", key=document_id, text=text, original=physical,
                                         source_url=str(document.get("source_url") or ""),
                                         byte_size=(service.originals / physical).stat().st_size)
                    # Migrated text is searchable lexically, but has no paid embedding job.
                    token = uuid4().hex
                    chunks = [{"id": uuid4().hex, "document_id": document_id, "token": token,
                               "chunk_index": index, "text": value}
                              for index, value in enumerate(chunks_for(text, 1000, 150))]
                    service._db.executemany("INSERT INTO chunks VALUES(:id,:document_id,:token,:chunk_index,:text)", chunks)
                    service._db.execute("UPDATE items SET active_token=?,chunk_count=? WHERE id=?",
                                         (token, len(chunks), document_id))
                    service._db.execute("INSERT INTO legacy_imports VALUES('document',?)", (document_id,))
    finally:
        source.close()
