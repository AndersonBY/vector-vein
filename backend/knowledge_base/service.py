from __future__ import annotations

import os
import math
import re
import sqlite3
import subprocess
import sys
import threading
import time
import zipfile
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .storage import KnowledgeError, acquire_owner, connect, identifier, name_value, now, safe_path, selected_metadata
from .vectors import EmbeddedVectors, checked_vectors
from .query import validate_query


MAX_BYTES = 50 * 1024 * 1024
MAX_TEXT = 4_000_000
MAX_ENTRIES = 2000
MAX_DEPTH = 20
ITEM_COLUMNS = (
    "id,kb_id,parent_id,kind,name,status,byte_size,original,source_url,generation,"
    "active_token,chunk_count,error_code,created_at,updated_at"
)
EXTENSIONS = {".txt", ".md", ".html", ".htm", ".json", ".csv", ".tsv", ".srt", ".pdf", ".docx", ".pptx", ".xlsx"}
ACTIONS = {
    "list", "get", "create", "update", "delete", "tree", "items", "create_folder",
    "import_files", "import_directory", "rename", "move", "delete_item", "preview",
    "open_file", "reindex", "search", "browse", "add_text", "get_item",
}


def default_embedder(base):
    from utilities.ai_utils import EmbeddingClient

    return EmbeddingClient(provider=base["embedding_provider"], model_id=base["embedding_model"],
                           dimensions=base["embedding_dimensions"])


def default_reranker():
    from utilities.ai_utils.rerank import configured_reranker

    return configured_reranker()


def default_extract(path):
    # Archives are deliberately not supported. Office containers are bounded before parsing.
    if path.suffix.lower() in {".docx", ".pptx", ".xlsx"}:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > 10000 or sum(info.file_size for info in infos) > 200 * 1024 * 1024:
                raise KnowledgeError("file_too_large", "The expanded document exceeds the extraction limit.")
    from utilities.file_processing.files import read_file_content

    return read_file_content(path, read_zip=False)


def chunks_for(text, size, overlap):
    step = size - overlap
    return [text[start:start + size] for start in range(0, len(text), step) if text[start:start + size].strip()]


def bounded_int(value, minimum, maximum, label):
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise KnowledgeError("invalid_input", f"{label} must be between {minimum} and {maximum}.")
    return value


class KnowledgeService:
    """SQLite is authoritative; Qdrant holds only derived, generation-scoped vectors.

    embedder_factory receives the KB record and returns an object exposing get(str/list).
    reranker_factory returns a vv-llm compatible client or None to disable reranking.
    start_worker=False permits explicit run_pending() in deterministic tests.
    """

    def __init__(self, root, *, embedder_factory=None, extractor=None, vector_store=None,
                 start_worker=True, legacy_path=None, opener=None, reranker_factory=None):
        self.root = safe_path(Path(root), exists=False)
        self.pid = os.getpid()
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._closed = False
        self._db = None
        self.vectors = None
        self._thread = None
        self._owner_file = acquire_owner(self.root)
        self.embedder_factory = embedder_factory or default_embedder
        self.reranker_factory = reranker_factory or default_reranker
        self.extractor = extractor or default_extract
        self.opener = opener or self._open_native
        try:
            self._db = connect(self.root)
            self.originals = safe_path(self.root / "originals", exists=False)
            self.originals.mkdir(exist_ok=True)
            self.vectors = vector_store if vector_store is not None else EmbeddedVectors(self.root / "vectors")
            with self._write():
                self._db.execute("UPDATE jobs SET status='queued',phase='queued',updated_at=? WHERE status='running'", (now(),))
                self._db.execute("UPDATE items SET status='queued' WHERE id IN (SELECT document_id FROM jobs WHERE status='queued')")
            if legacy_path is not None:
                from .migration import migrate_legacy

                migrate_legacy(self, Path(legacy_path))
            if start_worker:
                self.start()
        except BaseException:
            self.close()
            raise

    def start(self):
        with self._lock:
            self._assert_owner()
            if self._stop.is_set():
                raise KnowledgeError("service_unavailable", "Knowledge indexing is stopping.", 503)
            if self._thread is None:
                self._thread = threading.Thread(target=self._work_loop, name="knowledge-index", daemon=True)
                self._thread.start()
        return self

    def _assert_owner(self):
        if self.pid != os.getpid() or self._closed:
            raise KnowledgeError("service_unavailable", "The desktop knowledge service is unavailable.", 503)

    @contextmanager
    def _write(self):
        with self._lock:
            self._assert_owner()
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise

    def dispatch(self, action, payload=None):
        self._assert_owner()
        if not isinstance(action, str) or action not in ACTIONS or (payload is not None and not isinstance(payload, dict)):
            raise KnowledgeError("invalid_action", "Unknown knowledge base action.")
        try:
            return getattr(self, action)(**(payload or {}))
        except sqlite3.IntegrityError:
            raise KnowledgeError("name_conflict", "An item with this name already exists in this folder.", 409) from None
        except (TypeError, OverflowError):
            raise KnowledgeError("invalid_input", "Check the action fields and try again.") from None

    def _base(self, key):
        row = self._db.execute(
            "SELECT b.*, (SELECT count(*) FROM items WHERE kb_id=b.id AND kind='file') document_count FROM bases b WHERE id=?",
            (identifier(key),),
        ).fetchone()
        if row is None:
            raise KnowledgeError("not_found", "The knowledge base no longer exists.", 404)
        return dict(row)

    def _item(self, kb_id, key, *, include_text=False):
        columns = "*" if include_text else ITEM_COLUMNS
        row = self._db.execute(f"SELECT {columns} FROM items WHERE kb_id=? AND id=?", (identifier(kb_id), identifier(key))).fetchone()
        if row is None:
            raise KnowledgeError("not_found", "The item no longer exists in this knowledge base.", 404)
        return dict(row)

    def _parent(self, kb_id, parent_id):
        self._base(kb_id)
        if parent_id is not None:
            item = self._item(kb_id, parent_id)
            if item["kind"] != "folder":
                raise KnowledgeError("invalid_parent", "Choose a folder as the destination.")
            if len(self._path(item).split("/")) >= MAX_DEPTH:
                raise KnowledgeError("recursion_limit", "Folders can be nested at most 20 levels.")

    def _check_version(self, record, expected):
        if not isinstance(expected, str) or record["updated_at"] != expected:
            raise KnowledgeError("conflict", "The item changed. Refresh and try again.", 409)

    def _public_base(self, base):
        return {key: value for key, value in base.items() if key != "resolved_dimensions"}

    def _path(self, item):
        parts, current = [item["name"]], item
        seen = {item["id"]}
        while current["parent_id"]:
            current = self._db.execute(
                "SELECT id,name,parent_id FROM items WHERE kb_id=? AND id=?",
                (identifier(item["kb_id"]), identifier(current["parent_id"])),
            ).fetchone()
            if current is None:
                raise KnowledgeError("not_found", "The item no longer exists in this knowledge base.", 404)
            if current["id"] in seen:
                raise KnowledgeError("invalid_hierarchy", "The folder hierarchy needs repair.", 409)
            seen.add(current["id"])
            parts.append(current["name"])
        return "/".join(reversed(parts))

    def _public_item(self, item):
        result = {key: item[key] for key in (
            "id", "kb_id", "parent_id", "kind", "name", "status", "byte_size",
            "chunk_count", "error_code", "created_at", "updated_at",
            "source_url",
        )}
        result["path"] = self._path(item)
        job = self._db.execute(
            "SELECT phase,completed,total FROM jobs WHERE document_id=? AND generation=? ORDER BY created_at DESC LIMIT 1",
            (item["id"], item["generation"]),
        ).fetchone()
        if job:
            result["progress"] = dict(job)
        return result

    def list(self):
        with self._lock:
            return {"bases": [self._public_base(self._base(row["id"])) for row in
                              self._db.execute("SELECT id FROM bases ORDER BY created_at DESC").fetchall()]}

    def get(self, id):
        with self._lock:
            return self._public_base(self._base(id))

    def create(self, name, embedding_provider, embedding_model, description="", embedding_dimensions=None,
               chunk_size=1000, chunk_overlap=150):
        name = name_value(name)
        if not all(isinstance(value, str) and 0 < len(value.strip()) <= 200 for value in (embedding_provider, embedding_model)):
            raise KnowledgeError("invalid_model", "Select an embedding provider and model.")
        if not isinstance(description, str) or len(description) > 4000:
            raise KnowledgeError("invalid_input", "Description must be at most 4000 characters.")
        if embedding_dimensions is not None:
            bounded_int(embedding_dimensions, 1, 65536, "Embedding dimensions")
        bounded_int(chunk_size, 64, 16000, "Chunk size")
        bounded_int(chunk_overlap, 0, chunk_size - 1, "Chunk overlap")
        key, stamp = uuid4().hex, now()
        with self._write():
            self._db.execute(
                "INSERT INTO bases VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (key, name, description, embedding_provider.strip(), embedding_model.strip(), embedding_dimensions,
                 embedding_dimensions, chunk_size, chunk_overlap, stamp, stamp),
            )
            return self.get(key)

    def update(self, id, name, expected_updated_at, description=None):
        with self._write():
            base = self._base(id)
            self._check_version(base, expected_updated_at)
            if description is None:
                description = base["description"]
            if not isinstance(description, str) or len(description) > 4000:
                raise KnowledgeError("invalid_input", "Description must be at most 4000 characters.")
            self._db.execute("UPDATE bases SET name=?,description=?,updated_at=? WHERE id=?",
                             (name_value(name), description, now(), id))
            return self.get(id)

    def _descendants(self, kb_id, key=None):
        if key is None:
            return [dict(row) for row in self._db.execute(f"SELECT {ITEM_COLUMNS} FROM items WHERE kb_id=?", (kb_id,))]
        self._item(kb_id, key)
        columns = ",".join("i." + column for column in ITEM_COLUMNS.split(","))
        return [dict(row) for row in self._db.execute(f"""
            WITH RECURSIVE subtree(id) AS (
                SELECT id FROM items WHERE id=? AND kb_id=?
                UNION ALL SELECT i.id FROM items i JOIN subtree s ON i.parent_id=s.id WHERE i.kb_id=?
            ) SELECT {columns} FROM items i JOIN subtree s ON i.id=s.id
        """, (key, kb_id, kb_id))]

    def tree(self, kb_id):
        with self._lock:
            self._base(kb_id)
            rows = self._db.execute("SELECT id,name,parent_id FROM items WHERE kb_id=? AND kind='folder' ORDER BY name COLLATE NOCASE",
                                    (kb_id,)).fetchall()
            nodes = {row["id"]: {**dict(row), "children": []} for row in rows}
            roots = []
            for node in nodes.values():
                (nodes[node["parent_id"]]["children"] if node["parent_id"] else roots).append(node)
            return {"folders": roots}

    def items(self, kb_id, parent_id=None, search="", offset=0, limit=50):
        """Name search includes descendants of the selected folder; ordinary listing does not."""
        bounded_int(offset, 0, 1_000_000, "Offset")
        bounded_int(limit, 1, 200, "Limit")
        if not isinstance(search, str) or len(search) > 240:
            raise KnowledgeError("invalid_input", "Search must be at most 240 characters.")
        with self._lock:
            self._parent(kb_id, parent_id)
            if search:
                rows = [item for item in self._descendants(kb_id, parent_id)
                        if item["id"] != parent_id and search.casefold() in item["name"].casefold()]
            else:
                rows = [dict(row) for row in self._db.execute(
                    f"SELECT {ITEM_COLUMNS} FROM items WHERE kb_id=? AND parent_id IS ?", (kb_id, parent_id))]
            rows.sort(key=lambda item: (item["kind"] != "folder", item["name"].casefold(), item["id"]))
            breadcrumbs, current = [], parent_id
            while current:
                item = self._item(kb_id, current)
                breadcrumbs.append({"id": current, "name": item["name"]})
                current = item["parent_id"]
            return {"items": [self._public_item(item) for item in rows[offset:offset + limit]],
                    "total": len(rows), "breadcrumbs": list(reversed(breadcrumbs))}

    def _insert_item(self, kb_id, parent_id, name, kind, *, original=None, byte_size=0, key=None, text="", source_url=""):
        key, stamp = key or uuid4().hex, now()
        self._db.execute("""
            INSERT INTO items(id,kb_id,parent_id,kind,name,status,byte_size,original,source_url,extracted_text,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """, (key, kb_id, parent_id, kind, name, "ready" if kind == "folder" else "unindexed",
              byte_size, original, source_url, text, stamp, stamp))
        return key

    def get_item(self, kb_id, id):
        with self._lock:
            return self._public_item(self._item(kb_id, id))

    def add_text(self, kb_id, name, text, parent_id=None, source_url=""):
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
            raise KnowledgeError("invalid_text", "Provide nonempty text of at most four million characters.")
        if not isinstance(source_url, str) or len(source_url) > 4000:
            raise KnowledgeError("invalid_input", "The source URL must be at most 4000 characters.")
        key, physical = uuid4().hex, None
        try:
            with self._write():
                self._parent(kb_id, parent_id)
                clean_name = name_value(name)
                physical = self._text_original(key, text)
                self._insert_item(kb_id, parent_id, clean_name, "file", key=key, text=text,
                                  original=physical, byte_size=len(text.encode("utf-8")), source_url=source_url)
                self._queue(self._item(kb_id, key))
                result = self._public_item(self._item(kb_id, key))
        except BaseException:
            if physical is not None:
                safe_path(self.originals / physical).unlink(missing_ok=True)
            raise
        self._wake.set()
        return result

    def _text_original(self, key, text):
        physical = identifier(key) + ".txt"
        destination = safe_path(self.originals / physical, exists=False)
        created = False
        try:
            with destination.open("x", encoding="utf-8", newline="") as output:
                created = True
                output.write(text)
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            if created:
                destination.unlink(missing_ok=True)
            raise
        return physical

    def _copy_original(self, source, key):
        """Copy only the validated open file, rejecting changes and size growth."""
        physical = identifier(key) + source.suffix.lower()
        destination = safe_path(self.originals / physical, exists=False)
        created = False
        try:
            with source.open("rb") as reader, destination.open("xb") as writer:
                created = True
                before = os.fstat(reader.fileno())
                current = safe_path(source).stat()
                if (before.st_ino, before.st_dev) != (current.st_ino, current.st_dev):
                    raise KnowledgeError("source_changed", "The source changed during import. Try again.")
                total = 0
                while data := reader.read(1024 * 1024):
                    total += len(data)
                    if total > MAX_BYTES:
                        raise KnowledgeError("file_too_large", "Files must be at most 50 MiB.")
                    writer.write(data)
                after = os.fstat(reader.fileno())
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise KnowledgeError("source_changed", "The source changed during import. Try again.")
                writer.flush()
                os.fsync(writer.fileno())
            return physical, total
        except BaseException:
            if created:
                destination.unlink(missing_ok=True)
            raise

    def create_folder(self, kb_id, name, parent_id=None):
        with self._write():
            self._parent(kb_id, parent_id)
            key = self._insert_item(kb_id, parent_id, name_value(name), "folder")
            return self._public_item(self._item(kb_id, key))

    def rename(self, kb_id, id, name, expected_updated_at):
        with self._write():
            item = self._item(kb_id, id)
            self._check_version(item, expected_updated_at)
            self._db.execute("UPDATE items SET name=?,updated_at=? WHERE id=?", (name_value(name), now(), id))
            return self._public_item(self._item(kb_id, id))

    def move(self, kb_id, id, expected_updated_at, parent_id=None):
        with self._write():
            item = self._item(kb_id, id)
            self._check_version(item, expected_updated_at)
            self._parent(kb_id, parent_id)
            descendants = self._descendants(kb_id, id)
            if parent_id in {row["id"] for row in descendants}:
                raise KnowledgeError("folder_cycle", "A folder cannot be moved inside itself.")
            old_depth = len(self._path(item).split("/"))
            parent_depth = len(self._path(self._item(kb_id, parent_id)).split("/")) if parent_id else 0
            height = max(len(self._path(row).split("/")) - old_depth for row in descendants)
            if parent_depth + 1 + height > MAX_DEPTH:
                raise KnowledgeError("recursion_limit", "Folders can be nested at most 20 levels.")
            self._db.execute("UPDATE items SET parent_id=?,updated_at=? WHERE id=?", (parent_id, now(), id))
            return self._public_item(self._item(kb_id, id))

    def _original(self, item):
        if not item["original"]:
            raise KnowledgeError("original_unavailable", "This migrated document has extracted text only.")
        # Stored physical names are generated IDs, never logical names.
        if Path(item["original"]).name != item["original"]:
            raise KnowledgeError("unsafe_path", "The managed file path is invalid.")
        path = safe_path(self.originals / item["original"])
        if not path.is_file():
            raise KnowledgeError("file_missing", "The managed file is no longer available.", 404)
        return path

    def _source(self, raw, *, directory=False):
        if not isinstance(raw, str) or len(raw) > 4096 or "\x00" in raw or not Path(raw).is_absolute():
            raise KnowledgeError("unsafe_path", "Choose an absolute local file path.")
        path = safe_path(Path(raw))
        if path == self.root or self.root in path.parents:
            raise KnowledgeError("unsafe_path", "Choose source files outside managed knowledge storage.")
        if directory:
            if not path.is_dir():
                raise KnowledgeError("invalid_file", "Choose a local directory.")
        elif not path.is_file():
            raise KnowledgeError("invalid_file", "Choose a regular local file.")
        elif path.suffix.lower() not in EXTENSIONS:
            raise KnowledgeError("unsupported_type", "This document type is not supported.")
        elif path.stat().st_size > MAX_BYTES:
            raise KnowledgeError("file_too_large", "Files must be at most 50 MiB.")
        return path

    def _queue(self, document):
        stamp, token = now(), uuid4().hex
        generation = document["generation"] + 1
        self._db.execute("UPDATE jobs SET status='cancelled',updated_at=? WHERE document_id=? AND status IN ('queued','running')",
                         (stamp, document["id"]))
        self._db.execute("""
            UPDATE items SET generation=?,active_token=NULL,status='queued',error_code='',chunk_count=0,updated_at=? WHERE id=?
        """, (generation, stamp, document["id"]))
        self._db.execute("""
            INSERT INTO jobs(id,document_id,generation,status,phase,created_at,updated_at) VALUES(?,?,?,'queued','queued',?,?)
        """, (token, document["id"], generation, stamp, stamp))

    def _import_one(self, kb_id, parent_id, raw):
        source = self._source(raw)
        key = uuid4().hex
        physical = key + source.suffix.lower()
        destination = safe_path(self.originals / physical, exists=False)
        copied = False
        try:
            physical, total = self._copy_original(source, key)
            copied = True
            with self._write():
                self._parent(kb_id, parent_id)
                self._insert_item(kb_id, parent_id, name_value(source.name), "file",
                                  key=key, original=physical, byte_size=total)
                self._queue(self._item(kb_id, key))
                result = self._public_item(self._item(kb_id, key))
            self._wake.set()
            return result
        except BaseException:
            if copied:
                destination.unlink(missing_ok=True)
            raise

    def import_files(self, kb_id, paths, parent_id=None):
        if not isinstance(paths, list) or not 1 <= len(paths) <= MAX_ENTRIES:
            raise KnowledgeError("invalid_input", "Choose between 1 and 2000 files.")
        with self._lock:
            self._parent(kb_id, parent_id)
        items, skipped = [], []
        for raw in paths:
            try:
                items.append(self._import_one(kb_id, parent_id, raw))
            except (KnowledgeError, OSError, sqlite3.IntegrityError) as error:
                code = error.code if isinstance(error, KnowledgeError) else (
                    "name_conflict" if isinstance(error, sqlite3.IntegrityError) else "import_failed")
                skipped.append({"name": Path(raw).name if isinstance(raw, str) else "", "error_code": code})
        return {"items": items, "skipped": skipped}

    def import_directory(self, kb_id, path, parent_id=None):
        source = self._source(path, directory=True)
        items, skipped = [], []
        count, exhausted = 0, False

        def visit(directory, parent, depth):
            nonlocal count, exhausted
            if exhausted:
                return
            if depth > MAX_DEPTH:
                skipped.append({"name": directory.name, "error_code": "recursion_limit"})
                return
            safe_path(directory)
            # Reuse a same-name destination folder to make repeated imports useful.
            with self._write():
                self._parent(kb_id, parent)
                found = self._db.execute(
                    f"SELECT {ITEM_COLUMNS} FROM items WHERE kb_id=? AND parent_id IS ? AND name=? COLLATE NOCASE",
                    (kb_id, parent, directory.name)).fetchone()
                if found and found["kind"] != "folder":
                    raise KnowledgeError("name_conflict", "An item with this name already exists.", 409)
                folder_id = found["id"] if found else self._insert_item(kb_id, parent, name_value(directory.name), "folder")
                if not found:
                    items.append(self._public_item(self._item(kb_id, folder_id)))
            with os.scandir(directory) as entries:
                for entry in entries:
                    if exhausted:
                        return
                    if count >= MAX_ENTRIES:
                        exhausted = True
                        skipped.append({"name": directory.name, "error_code": "entry_limit"})
                        return
                    count += 1
                    try:
                        child = safe_path(Path(entry.path))
                        if entry.is_dir(follow_symlinks=False):
                            visit(child, folder_id, depth + 1)
                        else:
                            items.append(self._import_one(kb_id, folder_id, str(child)))
                    except (KnowledgeError, OSError, sqlite3.IntegrityError) as error:
                        skipped.append({"name": entry.name, "error_code": getattr(error, "code", "import_failed")})
        visit(source, parent_id, 0)
        return {"items": items, "skipped": skipped}

    def reindex(self, kb_id, id=None):
        with self._write():
            self._base(kb_id)
            documents = [item for item in self._descendants(kb_id, id) if item["kind"] == "file"]
            for document in documents:
                self._queue(document)
        self._wake.set()
        return {"queued_count": len(documents)}

    def _remove_originals(self, records):
        for item in records:
            if item["original"]:
                try:
                    self._original(item).unlink(missing_ok=True)
                except (KnowledgeError, OSError):
                    pass

    def delete_item(self, kb_id, id, expected_updated_at):
        with self._write():
            item = self._item(kb_id, id)
            self._check_version(item, expected_updated_at)
            records = self._descendants(kb_id, id)
            self._db.execute("DELETE FROM items WHERE id=?", (id,))
        self._remove_originals(records)
        # Logical invalidation commits first. An unavailable index cannot expose deleted data.
        with self._lock:
            for record in records:
                if record["kind"] == "file":
                    try:
                        self.vectors.delete_document(kb_id, record["id"])
                    except Exception:
                        pass
        return {"success": True}

    def delete(self, id, expected_updated_at):
        with self._write():
            base = self._base(id)
            self._check_version(base, expected_updated_at)
            records = self._descendants(id)
            self._db.execute("DELETE FROM bases WHERE id=?", (id,))
        self._remove_originals(records)
        with self._lock:
            try:
                self.vectors.delete_base(id)
            except Exception:
                pass
        return {"success": True}

    def preview(self, kb_id, id):
        with self._lock:
            item = self._item(kb_id, id, include_text=True)
            if item["kind"] != "file":
                raise KnowledgeError("invalid_file", "Choose a document to preview.")
            return {"item": self._public_item(item), "text": item["extracted_text"][:12000],
                    "truncated": len(item["extracted_text"]) > 12000}

    @staticmethod
    def _open_native(path):
        if sys.platform == "win32":
            os.startfile(str(path))
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def open_file(self, kb_id, id):
        with self._lock:
            path = self._original(self._item(kb_id, id))
            try:
                self.opener(path)
            except Exception:
                raise KnowledgeError("open_failed", "Could not open the document in its default application.") from None
            return {"success": True}

    def selected_bases(self, ids):
        return selected_metadata(self.root, ids)

    def browse(self, kb_ids, folder_id=None, offset=0, limit=50):
        """List one metadata-only level; truncated marks an unreachable next offset above 10000."""
        bounded_int(offset, 0, 10000, "Offset")
        bounded_int(limit, 1, 50, "Limit")
        with self._lock:
            self._assert_owner()
            selected = self.selected_bases(kb_ids)
            if not selected:
                raise KnowledgeError("invalid_scope", "Select between 1 and 20 knowledge bases.")
            bases = {base["kb_id"]: {**base, "document_count": 0, "keyword_documents": 0,
                                    "semantic_documents": 0, "status_counts": {}}
                     for base in sorted(selected, key=lambda base: base["kb_id"])}
            prefix = ""
            if folder_id is not None:
                folder = self._db.execute(
                    "SELECT id,kb_id,parent_id,name FROM items WHERE id=? AND kind='folder'",
                    (identifier(folder_id),),
                ).fetchone()
                if folder is None or folder["kb_id"] not in bases:
                    raise KnowledgeError("invalid_scope", "The folder must belong to a selected knowledge base.")
                prefix = self._path(folder) + "/"
            scope = "kb_id IN (" + ",".join("?" for _ in bases) + ")"
            scope_args = list(bases)
            counts = self._db.execute("""
                SELECT i.kb_id,i.status,count(*) AS document_count,
                       sum(coalesce(i.active_token,'')<>'' AND EXISTS (
                           SELECT 1 FROM chunks c WHERE c.document_id=i.id AND c.token=i.active_token
                       )) AS keyword_documents
                FROM items i WHERE i.kind='file' AND """ + scope + " GROUP BY i.kb_id,i.status", scope_args)
            for row in counts:
                base = bases[row["kb_id"]]
                base["document_count"] += row["document_count"]
                base["status_counts"][row["status"]] = row["document_count"]
                base["keyword_documents"] += row["keyword_documents"]
                if row["status"] == "ready":
                    base["semantic_documents"] += row["keyword_documents"]
            where = scope + " AND parent_id IS ?"
            args = [*scope_args, folder_id]
            total = self._db.execute("SELECT count(*) FROM items WHERE " + where, args).fetchone()[0]
            rows = self._db.execute(
                "SELECT id,kb_id,parent_id,kind,name,status,chunk_count,error_code FROM items WHERE " + where
                + " ORDER BY kb_id,CASE kind WHEN 'folder' THEN 0 ELSE 1 END,name COLLATE NOCASE,id LIMIT ? OFFSET ?",
                [*args, limit, offset],
            )
            items = [{**dict(row), "path": prefix + row["name"]} for row in rows]
            next_offset = offset + len(items)
            has_more = next_offset < total
            return {"bases": list(bases.values()), "items": items, "total": total, "offset": offset, "limit": limit,
                    "next_offset": next_offset if has_more and next_offset <= 10000 else None,
                    "truncated": has_more and next_offset > 10000}

    def read_document(self, kb_ids, document_id, offset=0, limit=12000):
        self._assert_owner()
        bounded_int(offset, 0, MAX_TEXT, "Offset")
        bounded_int(limit, 1, 12000, "Limit")
        with self._lock:
            scope = self.selected_bases(kb_ids)
            row = self._db.execute("SELECT * FROM items WHERE id=? AND kind='file'", (identifier(document_id),)).fetchone()
            if row is None or row["kb_id"] not in {base["kb_id"] for base in scope}:
                raise KnowledgeError("not_found", "The document is not available in the selected knowledge bases.", 404)
            item = dict(row)
            text = item["extracted_text"]
            return {"kb_id": item["kb_id"], "document_id": item["id"], "document_name": item["name"],
                    "path": self._path(item), "text": text[offset:offset + limit], "offset": offset,
                    "total": len(text), "truncated": offset + limit < len(text), "status": item["status"]}

    def _eligible(self, kb_ids, folder_id):
        bases = [self._base(value) for value in kb_ids]
        allowed = None
        if folder_id is not None:
            row = self._db.execute(f"SELECT {ITEM_COLUMNS} FROM items WHERE id=? AND kind='folder'", (identifier(folder_id),)).fetchone()
            if row is None or row["kb_id"] not in kb_ids:
                raise KnowledgeError("invalid_scope", "The folder must belong to a selected knowledge base.")
            allowed = {item["id"] for item in self._descendants(row["kb_id"], folder_id)}
        documents = {}
        for base in bases:
            for row in self._db.execute(f"SELECT {ITEM_COLUMNS} FROM items WHERE kb_id=? AND kind='file'", (base["id"],)):
                if allowed is None or row["id"] in allowed:
                    documents[row["id"]] = dict(row)
        return bases, documents

    def search(self, kb_ids, query, mode="hybrid", folder_id=None, limit=10):
        query = validate_query(query)
        self.selected_bases(kb_ids)
        if mode not in {"keyword", "semantic", "hybrid"}:
            raise KnowledgeError("invalid_mode", "Choose keyword, semantic or hybrid search.")
        bounded_int(limit, 1, 50, "Limit")
        candidate_limit = min(limit * 4, 200)
        warnings, rankings = {}, []
        with self._lock:
            bases, documents = self._eligible(kb_ids, folder_id)
            for document in documents.values():
                if document["status"] == "ready":
                    continue
                warning = warnings.setdefault(document["kb_id"], {
                    "kb_id": document["kb_id"], "count": 0, "counts": {},
                    "error_code": "unindexed",
                    "message": "Some documents are not fully indexed. Reindex or retry to enable semantic retrieval.",
                })
                warning["count"] += 1
                counts = warning["counts"]
                counts[document["status"]] = counts.get(document["status"], 0) + 1
                if document["status"] != "unindexed":
                    warning["error_code"] = "index_incomplete"
            scope_sql = "i.kb_id IN (" + ",".join("?" for _ in kb_ids) + ")"
            scope_args = list(kb_ids)
            if folder_id is not None:
                scope_sql += """ AND i.id IN (
                    WITH RECURSIVE subtree(id) AS (
                        SELECT ? UNION ALL SELECT child.id FROM items child JOIN subtree s ON child.parent_id=s.id
                    ) SELECT id FROM subtree
                )"""
                scope_args.append(folder_id)
            join_sql = " JOIN items i ON i.id=c.document_id AND i.active_token=c.token "
            if mode in {"keyword", "hybrid"}:
                # Trigram FTS supports Chinese without a tokenizer dictionary. Short terms use
                # a bound instr() scan, since FTS trigram has no tokens under three characters.
                terms = re.findall(r"\w+", query.casefold(), re.UNICODE)[:32]
                ranked = []
                if any(len(term) >= 3 for term in terms):
                    expression = " OR ".join('"' + term.replace('"', '""') + '"' for term in terms if len(term) >= 3)
                    ranked = [row[0] for row in self._db.execute(
                        "SELECT c.id FROM chunk_fts JOIN chunks c ON c.id=chunk_fts.chunk_id" + join_sql
                        + "WHERE chunk_fts MATCH ? AND " + scope_sql
                        + " ORDER BY bm25(chunk_fts),c.id LIMIT ?", [expression, *scope_args, candidate_limit])]
                short_terms = [term for term in terms if len(term) < 3]
                if short_terms:
                    fallback = self._db.execute(
                        "SELECT c.id FROM chunks c" + join_sql + "WHERE " + scope_sql + " AND ("
                        + " OR ".join("instr(lower(c.text),?)>0" for _ in short_terms)
                        + ") ORDER BY c.chunk_index,c.id LIMIT ?", [*scope_args, *short_terms, candidate_limit])
                    seen = set(ranked)
                    ranked.extend(row[0] for row in fallback if row[0] not in seen)
                rankings.append(ranked[:candidate_limit])
        if mode in {"semantic", "hybrid"}:
            for base in bases:
                active = [item["active_token"] for item in documents.values()
                          if item["kb_id"] == base["id"] and item["status"] == "ready" and item["active_token"]]
                if not active:
                    continue
                try:
                    vector = checked_vectors([self.embedder_factory(base).get(query)], 1,
                                             base["resolved_dimensions"] or base["embedding_dimensions"])[0]
                    with self._lock:
                        self._assert_owner()
                        rankings.append(self.vectors.search(base["id"], vector, active, candidate_limit))
                except Exception:
                    warning = warnings.setdefault(base["id"], {"kb_id": base["id"], "count": 0, "counts": {}})
                    warning["count"] += len(active)
                    warning["counts"]["semantic_unavailable"] = len(active)
                    warning.update(error_code="semantic_unavailable",
                                   message="Semantic search is unavailable. Check the embedding model and retry.")
        scores = {}
        for ranking in rankings:
            for rank, key in enumerate(dict.fromkeys(ranking), 1):
                scores[key] = scores.get(key, 0.0) + 1.0 / (60 + rank)
        with self._lock:
            # Revalidate after provider calls, which may overlap deletion, reindex or moves.
            _, current = self._eligible(kb_ids, folder_id)
            results = []
            revisions = {}
            base_names = {base["id"]: base["name"] for base in bases}
            for key in sorted(scores, key=lambda key: (-scores[key], key)):
                chunk = self._db.execute(
                    "SELECT c.* FROM chunks c" + join_sql + " WHERE c.id=? AND " + scope_sql,
                    [key, *scope_args],
                ).fetchone()
                if chunk is None:
                    continue
                document = current.get(chunk["document_id"])
                if document is None or document["active_token"] != chunk["token"]:
                    continue
                results.append({
                    "kb_id": document["kb_id"], "kb_name": base_names[document["kb_id"]],
                    "document_id": document["id"], "document_name": document["name"], "path": self._path(document),
                    "chunk_id": key, "chunk_index": chunk["chunk_index"], "text": chunk["text"], "score": scores[key],
                })
                revisions[key] = (document["active_token"], document["generation"])
                if len(results) == candidate_limit:
                    break
        rerank_warning = []
        if results:
            try:
                # Neither client construction nor provider IO holds the metadata lock.
                reranker = self.reranker_factory()
                if reranker is not None:
                    response = reranker.rerank(
                        query=query, documents=[hit["text"] for hit in results],
                        top_n=len(results), return_documents=False, timeout=30,
                    )
                    ranked = response.results
                    if not isinstance(ranked, list) or not ranked:
                        raise ValueError("Empty rerank results")
                    seen, reordered = set(), []
                    for item in ranked:
                        index, score = item.index, item.relevance_score
                        if (type(index) is not int or not 0 <= index < len(results) or index in seen
                                or isinstance(score, bool) or not isinstance(score, (int, float))
                                or not math.isfinite(score)):
                            raise ValueError("Invalid rerank result")
                        seen.add(index)
                        reordered.append({**results[index], "score": score})
                    # Partial top-N responses retain all remaining original candidates.
                    results = reordered + [hit for index, hit in enumerate(results) if index not in seen]
            except Exception:
                rerank_warning = [{
                    "error_code": "rerank_unavailable",
                    "message": "Reranking is unavailable or returned invalid results. Original retrieval order was retained. Check the rerank model and endpoint.",
                }]
        with self._lock:
            # Provider output never supplies content. Refresh scope, generation and metadata.
            try:
                current_bases, current = self._eligible(kb_ids, folder_id)
            except KnowledgeError:
                current_bases, current = [], {}
            base_names = {base["id"]: base["name"] for base in current_bases}
            fresh = []
            for hit in results:
                document = current.get(hit["document_id"])
                if document is None or revisions[hit["chunk_id"]] != (document["active_token"], document["generation"]):
                    continue
                fresh.append({**hit, "kb_name": base_names[document["kb_id"]],
                              "document_name": document["name"], "path": self._path(document)})
                if len(fresh) == limit:
                    break
        return {"results": fresh, "warnings": [
            warnings[base["id"]] for base in bases if base["id"] in warnings] + rerank_warning}

    def _work_loop(self):
        try:
            while not self._stop.is_set():
                try:
                    if self.run_pending(max_jobs=1):
                        continue
                except Exception:
                    # Storage failures are retried without logging document/provider contents.
                    pass
                self._wake.wait(0.5)
                self._wake.clear()
        finally:
            self._finish_close()

    def _current_job(self, job, *, include_text=False):
        columns = "i.*" if include_text else ",".join("i." + column for column in ITEM_COLUMNS.split(","))
        row = self._db.execute(f"""
            SELECT {columns} FROM items i JOIN jobs j ON j.document_id=i.id
            WHERE j.id=? AND j.status='running' AND i.generation=j.generation
        """, (job["id"],)).fetchone()
        return dict(row) if row is not None and not self._stop.is_set() else None

    def run_pending(self, max_jobs=1000):
        self._assert_owner()
        completed = 0
        for _ in range(max_jobs):
            if self._stop.is_set():
                break
            with self._write():
                row = self._db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
                if row is None:
                    break
                job = dict(row)
                self._db.execute("UPDATE jobs SET status='running',phase='extracting',updated_at=? WHERE id=?", (now(), job["id"]))
                self._db.execute("UPDATE items SET status='indexing',updated_at=? WHERE id=?", (now(), job["document_id"]))
            self._index(job)
            completed += 1
        return completed

    def _index(self, job):
        try:
            with self._lock:
                document = self._current_job(job, include_text=True)
                if document is None:
                    return
                base = self._base(document["kb_id"])
                original = self._original(document) if document["original"] else None
            try:
                text = self.extractor(original) if original else document["extracted_text"]
            except KnowledgeError:
                raise
            except Exception:
                raise KnowledgeError("extraction_failed", "The document could not be extracted.") from None
            if not isinstance(text, str) or not text.strip():
                raise KnowledgeError("empty_document", "The document has no extractable text.")
            if len(text) > MAX_TEXT:
                raise KnowledgeError("text_too_large", "The extracted document exceeds four million characters.")
            texts = chunks_for(text, base["chunk_size"], base["chunk_overlap"])
            chunks = [{"id": uuid4().hex, "document_id": document["id"], "token": job["id"],
                       "chunk_index": index, "text": value} for index, value in enumerate(texts)]
            with self._write():
                if self._current_job(job) is None:
                    return
                self._db.execute("UPDATE items SET extracted_text=? WHERE id=?", (text, document["id"]))
                self._db.execute("DELETE FROM chunks WHERE document_id=? AND token=?", (document["id"], job["id"]))
                self._db.executemany("INSERT INTO chunks VALUES(:id,:document_id,:token,:chunk_index,:text)", chunks)
                # Extraction is an independently useful publication. Provider failures must
                # not hide current keyword evidence; semantic retrieval still requires ready.
                self._db.execute("UPDATE items SET active_token=?,chunk_count=? WHERE id=?",
                                 (job["id"], len(chunks), document["id"]))
                self._db.execute("DELETE FROM chunks WHERE document_id=? AND token<>?", (document["id"], job["id"]))
                self._db.execute("UPDATE jobs SET phase='embedding',total=?,completed=0,updated_at=? WHERE id=?",
                                 (len(chunks), now(), job["id"]))
            with self._lock:
                if self._current_job(job) is None:
                    return
                # A resumed attempt may have persisted only some Qdrant batches.
                # Reclaim those derived points before retrying, including obsolete IDs.
                self.vectors.delete_document(base["id"], document["id"])
            try:
                embedder = self.embedder_factory(base)
            except Exception:
                raise KnowledgeError("embedding_unavailable", "Check the configured embedding provider and retry.") from None
            dimension = base["resolved_dimensions"] or base["embedding_dimensions"]
            for offset in range(0, len(chunks), 32):
                with self._lock:
                    if self._current_job(job) is None:
                        return
                batch = chunks[offset:offset + 32]
                try:
                    response = embedder.get([chunk["text"] for chunk in batch])
                except Exception:
                    raise KnowledgeError("embedding_failed", "Embedding failed. Check the configured model and retry.") from None
                vectors = checked_vectors(response, len(batch), dimension)
                dimension = len(vectors[0])
                with self._lock:
                    if self._current_job(job) is None:
                        return
                    self.vectors.write(base["id"], dimension, batch, vectors, job["id"])
                    with self._write():
                        self._db.execute("UPDATE bases SET resolved_dimensions=? WHERE id=?", (dimension, base["id"]))
                        self._db.execute("UPDATE jobs SET completed=?,updated_at=? WHERE id=?",
                                         (offset + len(batch), now(), job["id"]))
            with self._write():
                if self._current_job(job) is None:
                    return
                self._db.execute("UPDATE jobs SET phase='publishing',updated_at=? WHERE id=?", (now(), job["id"]))
            # The Qdrant calls above are durable before the SQLite publication transaction.
            with self._write():
                if self._current_job(job) is None:
                    return
                self._db.execute("""
                    UPDATE items SET status='ready',active_token=?,chunk_count=?,error_code='',updated_at=? WHERE id=?
                """, (job["id"], len(chunks), now(), document["id"]))
                self._db.execute("DELETE FROM chunks WHERE document_id=? AND token<>?", (document["id"], job["id"]))
                self._db.execute("UPDATE jobs SET status='completed',phase='completed',updated_at=? WHERE id=?", (now(), job["id"]))
        except Exception as error:
            with self._write():
                if self._current_job(job) is not None:
                    code = error.code if isinstance(error, KnowledgeError) else "indexing_failed"
                    self._db.execute("UPDATE items SET status='failed',error_code=?,updated_at=? WHERE id=?",
                                     (code, now(), job["document_id"]))
                    self._db.execute("UPDATE jobs SET status='failed',phase='failed',error_code=?,updated_at=? WHERE id=?",
                                     (code, now(), job["id"]))

    def wait_idle(self, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if not self._db.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running') LIMIT 1").fetchone():
                    return
            time.sleep(0.02)
        raise TimeoutError("Knowledge indexing did not finish in time.")

    def close(self):
        if self._closed:
            return
        self._stop.set()
        self._wake.set()
        if self._thread is not None and self._thread.ident is not None:
            # Provider calls cannot safely be killed. Let a daemon finish without closing
            # its database underneath it; a later close can complete resource release.
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                return
        self._finish_close()

    stop = close

    def _finish_close(self):
        with self._lock:
            if self._closed:
                return
            if self.vectors is not None:
                self.vectors.close()
            if self._db is not None:
                self._db.close()
            if self._owner_file is not None:
                # The worker and both stores have finished before ownership can pass.
                self._owner_file.close()
                self._owner_file = None
            self._closed = True
