"""Fail-closed, whole-directory backup before the destructive v1 migration."""
from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import tempfile
import time
from uuid import uuid4
import zipfile


class UpgradeBackupError(RuntimeError):
    """The upgrade must stop because its recovery backup is unavailable."""


MARKER = ".v1-upgrade-backup.json"
TIMEOUT = 30.0
CHUNK = 1024 * 1024
MIGRATION = "006_remove_conversation_agent"


def _plain(path):
    info = path.lstat()
    if getattr(info, "st_file_attributes", 0) & 0x400:
        raise UpgradeBackupError("Upgrade stopped: reparse points cannot be backed up safely.")
    if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
        raise UpgradeBackupError("Upgrade stopped: links and special files are not supported.")
    return info


def _ancestors(path):
    for item in reversed((path, *path.parents)):
        if item.exists() or item.is_symlink():
            _plain(item)


def _signature(info):
    # Windows 3.12 path stat uses creation time; CRT fstat uses change time.
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns if os.name != "nt" else None)


@contextmanager
def _reader(path):
    _ancestors(path)
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = Path(str(path) + suffix)
        if sidecar.exists() or sidecar.is_symlink():
            _plain(sidecar)
    uri = path.as_uri() + "?mode=ro"
    # A fully checkpointed WAL database otherwise creates empty WAL/SHM files
    # even for a read-only connection. Immutable is safe only with no live WAL;
    # the surrounding source manifests reject a concurrent writer appearing.
    with path.open("rb") as handle:
        wal_mode = handle.read(20)[18:20] == b"\x02\x02"
    if wal_mode and not Path(str(path) + "-wal").exists() and not Path(str(path) + "-journal").exists():
        uri += "&immutable=1"
    connection = sqlite3.connect(uri, uri=True, timeout=1)
    deadline = time.monotonic() + TIMEOUT
    connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
    try:
        yield connection
    finally:
        connection.close()


def _needed(path, legacy_only):
    with _reader(path) as connection:
        tables = {row[0].lower() for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if "migratehistory" in tables and connection.execute(
            "SELECT 1 FROM migratehistory WHERE name=? LIMIT 1", (MIGRATION,)
        ).fetchone():
            return False
        if legacy_only:
            return bool(tables & {"agent", "conversation", "message", "chatdraft"}) or (
                "workflowrunrecord" in tables and any(
                    row[1].lower() == "source_message"
                    for row in connection.execute("PRAGMA table_info(workflowrunrecord)")
                )
            )
        return bool({table for table in tables if table != "migratehistory"
                     and not table.startswith("sqlite_")})


@contextmanager
def _lock(path):
    # Keep the lock inode permanently: removing it permits concurrent lock owners.
    if path.exists() or path.is_symlink():
        _plain(path)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "r+b") as handle:
        _plain(path)
        deadline = time.monotonic() + TIMEOUT
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise UpgradeBackupError("Upgrade stopped: backup lock timed out.") from None
                time.sleep(0.05)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _inventory(root):
    entries = {}
    def visit(path):
        info = _plain(path)
        entries[path] = info
        if stat.S_ISDIR(info.st_mode):
            for child in sorted(path.iterdir()):
                visit(child)
    visit(root)
    return entries


def _open_file(path, expected):
    _ancestors(path)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
    handle = os.fdopen(descriptor, "rb")
    if _signature(os.fstat(handle.fileno())) != _signature(expected):
        handle.close()
        raise UpgradeBackupError("Upgrade stopped: a source file changed during backup.")
    return handle


def _snapshot(source, target):
    deadline = time.monotonic() + TIMEOUT
    def progress(status, remaining, total):
        if time.monotonic() >= deadline:
            raise UpgradeBackupError("Upgrade stopped: SQLite backup timed out.")
    with _reader(source) as connection, closing(sqlite3.connect(target)) as destination:
        with destination:
            connection.backup(destination, pages=256, progress=progress, sleep=0.05)
            destination.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            if destination.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise UpgradeBackupError("Upgrade stopped: SQLite snapshot failed integrity verification.")


def _hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify(path):
    _plain(path)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise UpgradeBackupError("Upgrade stopped: backup ZIP failed CRC verification.")


def _publish(partial, final):
    # Windows rename is atomic and refuses an existing target, including on
    # portable filesystems without hard links. POSIX rename would overwrite.
    if os.name == "nt":
        os.rename(partial, final)
    else:
        os.link(partial, final)


def _manifest(root, entries):
    shared_memory = set()
    fingerprints = {}
    for path, info in entries.items():
        if stat.S_ISREG(info.st_mode) and path != root / MARKER:
            with _open_file(path, info) as handle:
                if handle.read(16) == b"SQLite format 3\0":
                    shared_memory.add(Path(str(path) + "-shm"))
    for path, info in entries.items():
        if stat.S_ISREG(info.st_mode) and path != root / MARKER and path not in shared_memory:
            digest = hashlib.sha256()
            with _open_file(path, info) as handle:
                for block in iter(lambda: handle.read(CHUNK), b""):
                    digest.update(block)
                if _signature(os.fstat(handle.fileno())) != _signature(info):
                    raise UpgradeBackupError("Upgrade stopped: a source file changed during backup.")
            fingerprints[path] = digest.hexdigest()
    return {
        path.relative_to(root).as_posix(): [*_signature(info), fingerprints[path]]
        for path, info in entries.items()
        if path != root / MARKER and path not in shared_memory
        and stat.S_ISREG(info.st_mode)
    } | {
        path.relative_to(root).as_posix() + "/": None
        for path, info in entries.items() if stat.S_ISDIR(info.st_mode)
    }


def _reuse(root):
    marker = root / MARKER
    if not marker.exists():
        return None
    _plain(marker)
    try:
        if marker.stat().st_size > 64 * 1024 * 1024:
            return None
        data = json.loads(marker.read_text(encoding="utf-8"))
        name = data["backup"]
        pattern = re.escape(root.name) + r"-backup-before-v1\.0\.0-\d{8}T\d{12}Z-[0-9a-f]{32}\.zip"
        if data["version"] != "1.0.0" or not isinstance(name, str) or not re.fullmatch(pattern, name):
            return None
        if data.get("source_manifest") != _manifest(root, _inventory(root)):
            return None
        path = root.parent / name
        _verify(path)
        if _hash(path) == data["sha256"]:
            return path
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile):
        pass
    return None


def _create(root, database_path):
    entries = _inventory(root)
    source_manifest = _manifest(root, entries)
    databases = set()
    for path, info in entries.items():
        if stat.S_ISREG(info.st_mode) and path != root / MARKER:
            with _open_file(path, info) as handle:
                if handle.read(16) == b"SQLite format 3\0":
                    databases.add(path)
    if database_path not in databases:
        raise UpgradeBackupError("Upgrade stopped: the configured database is not readable SQLite.")
    sidecars = {Path(str(path) + suffix) for path in databases
                for suffix in ("-wal", "-shm", "-journal")}
    name = (f"{root.name}-backup-before-v1.0.0-"
            f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}-{uuid4().hex}.zip")
    final = root.parent / name
    # All temporary files are outside the archived directory.
    with tempfile.TemporaryDirectory(prefix=".v1-backup-", dir=root.parent) as temporary:
        temporary = Path(temporary)
        partial = temporary / (name + ".partial")
        with zipfile.ZipFile(partial, "x", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            for path, info in entries.items():
                arcname = path.relative_to(root.parent).as_posix()
                if stat.S_ISDIR(info.st_mode):
                    member = zipfile.ZipInfo.from_file(path, arcname, strict_timestamps=False)
                    member.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(member, b"")
                elif path not in sidecars and path != root / MARKER:
                    member = zipfile.ZipInfo.from_file(path, arcname, strict_timestamps=False)
                    member.compress_type = zipfile.ZIP_DEFLATED
                    source = path
                    if path in databases:
                        source = temporary / (uuid4().hex + ".db")
                        _snapshot(path, source)
                    with (_open_file(path, info) if source == path else source.open("rb")) as incoming:
                        with archive.open(member, "w", force_zip64=True) as outgoing:
                            shutil.copyfileobj(incoming, outgoing, CHUNK)
                        if source == path and _signature(os.fstat(incoming.fileno())) != _signature(info):
                            raise UpgradeBackupError("Upgrade stopped: a source file changed during backup.")
        after = _inventory(root)
        # Never certify a newer source manifest against an older snapshot.
        if source_manifest != _manifest(root, after):
            raise UpgradeBackupError("Upgrade stopped: the data directory changed during backup.")
        _verify(partial)
        digest = _hash(partial)
        os.chmod(partial, 0o600)
        with partial.open("r+b") as handle:
            os.fsync(handle.fileno())
        _publish(partial, final)
        marker_temp = temporary / "marker"
        with marker_temp.open("x", encoding="utf-8") as handle:
            os.chmod(marker_temp, 0o600)
            json.dump({"version": "1.0.0", "backup": name, "sha256": digest,
                       "source_manifest": source_manifest}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(marker_temp, root / MARKER)
    return final


def ensure_v1_upgrade_backup(database, *, legacy_only=False) -> Path | None:
    """Return a verified recovery ZIP, or None for a new/already migrated DB.

    Call before the first migration write. Errors must abort upgrade.
    No models/config imports or source checkpoints are performed here.
    """
    try:
        raw = os.fspath(database.database)
        if raw == ":memory:":
            return None
        path = Path(os.path.abspath(raw))
        root = path.parent
        if root == root.parent:
            raise UpgradeBackupError(
                "Upgrade stopped: the data directory must not be a drive or filesystem root. "
                "Configure a dedicated data directory before retrying."
            )
        _ancestors(root)
        if not path.exists():
            return None
        _plain(path)
        if not _needed(path, legacy_only):
            return None
        with _lock(root.parent / f".{root.name}-v1-upgrade-backup.lock"):
            if not _needed(path, legacy_only):
                return None
            # Validate the entire tree even when reusing a previously saved ZIP.
            _inventory(root)
            return _reuse(root) or _create(root, path)
    except UpgradeBackupError:
        raise
    except Exception:
        raise UpgradeBackupError(
            "Upgrade stopped: a verified v1.0.0 data backup could not be created. "
            "Check local storage space, permissions and database availability, then retry."
        ) from None


def ensure_workspace_v1_upgrade_backup(workspace: Path | str | None = None) -> Path | None:
    """Read only the workspace configuration before importing application state."""
    try:
        from peewee import SqliteDatabase

        workspace = Path(os.path.abspath(workspace if workspace is not None else os.getcwd()))
        _ancestors(workspace)
        config_path = workspace / "config.json"
        data_path = "./data"
        if config_path.exists() or config_path.is_symlink():
            _plain(config_path)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            data_path = config.get("data_path", "./data")
            if not isinstance(data_path, str) or not data_path.strip():
                raise ValueError("Invalid data directory")
        path = Path(data_path)
        if not path.is_absolute():
            path = workspace / path
        return ensure_v1_upgrade_backup(SqliteDatabase(path / "my_database.db"))
    except UpgradeBackupError:
        raise
    except Exception:
        raise UpgradeBackupError(
            "Upgrade stopped: the workspace data location could not be read safely. "
            "Check config.json and local permissions before retrying."
        ) from None
