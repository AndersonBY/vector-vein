from concurrent.futures import ProcessPoolExecutor
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import time
import zipfile

from peewee import SqliteDatabase
import pytest

from utilities import upgrade_backup as backup


def old_database(tmp_path, name="custom-store", legacy=True):
    root = tmp_path / name
    root.mkdir()
    path = root / "my_database.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE workflow (title TEXT)")
        if legacy:
            connection.execute("CREATE TABLE message (content TEXT)")
            connection.execute("INSERT INTO message VALUES ('synthetic chat')")
    return root, SqliteDatabase(path)


def run_backup(path):
    return str(backup.ensure_v1_upgrade_backup(SqliteDatabase(path)))


def test_whole_custom_directory_and_all_sqlite_snapshots(tmp_path):
    root, database = old_database(tmp_path)
    (root / "static" / "attachments").mkdir(parents=True)
    (root / "static" / "attachments" / "example.txt").write_bytes(b"synthetic attachment")
    (root / "empty").mkdir()
    nested = root / "knowledge-base"
    nested.mkdir()
    (nested / backup.MARKER).write_bytes(b"ordinary nested file")
    with sqlite3.connect(nested / "index.bin") as connection:
        connection.execute("CREATE TABLE chunks (text TEXT)")
        connection.execute("INSERT INTO chunks VALUES ('synthetic knowledge')")
    result = backup.ensure_v1_upgrade_backup(database)
    assert result.parent == tmp_path
    assert result.name.startswith("custom-store-backup-before-v1.0.0-")
    with zipfile.ZipFile(result) as archive:
        assert archive.testzip() is None
        assert archive.read("custom-store/static/attachments/example.txt") == b"synthetic attachment"
        assert archive.read(f"custom-store/knowledge-base/{backup.MARKER}") == b"ordinary nested file"
        assert "custom-store/empty/" in archive.namelist()
        assert f"custom-store/{backup.MARKER}" not in archive.namelist()
        archive.extractall(tmp_path / "restore")
    with sqlite3.connect(tmp_path / "restore/custom-store/knowledge-base/index.bin") as connection:
        assert connection.execute("SELECT * FROM chunks").fetchall() == [("synthetic knowledge",)]
    marker = json.loads((root / backup.MARKER).read_text())
    assert marker["sha256"] == backup._hash(result)
    assert backup.ensure_v1_upgrade_backup(database) == result
    assert len(list(tmp_path.glob("*.zip"))) == 1


def test_zip_preserves_source_times_and_modes_including_sqlite_snapshot(tmp_path):
    root, database = old_database(tmp_path)
    directory = root / "attachments"
    directory.mkdir()
    attachment = directory / "example.txt"
    attachment.write_bytes(b"synthetic attachment")
    paths = (attachment, Path(database.database), directory)
    expected = {}
    for index, path in enumerate(paths):
        timestamp = 1660000001 + index * 60
        os.utime(path, (timestamp, timestamp))
        info = path.stat()
        local = time.localtime(info.st_mtime)
        # ZIP's DOS timestamp stores local time at two-second precision.
        date_time = (*local[:5], local.tm_sec // 2 * 2)
        expected[path.relative_to(root.parent).as_posix() + ("/" if path.is_dir() else "")] = (
            date_time, info.st_mode & 0xFFFF,
        )
    result = backup.ensure_v1_upgrade_backup(database)
    with zipfile.ZipFile(result) as archive:
        for name, (date_time, mode) in expected.items():
            member = archive.getinfo(name)
            assert member.date_time == date_time
            assert member.external_attr >> 16 == mode
            assert member.compress_type == zipfile.ZIP_DEFLATED
        assert archive.read(f"{root.name}/attachments/example.txt") == b"synthetic attachment"


@pytest.mark.parametrize("state", ["missing", "empty", "history_only", "done", "memory"])
def test_new_or_completed_databases_skip(tmp_path, state):
    root = tmp_path / "data"
    root.mkdir()
    path = root / "my_database.db"
    database = SqliteDatabase(":memory:" if state == "memory" else path)
    if state not in {"missing", "memory"}:
        with sqlite3.connect(path) as connection:
            if state in {"history_only", "done"}:
                connection.execute("CREATE TABLE migratehistory (name TEXT)")
            if state == "done":
                connection.execute("CREATE TABLE message (content TEXT)")
                connection.execute("INSERT INTO migratehistory VALUES (?)", (backup.MIGRATION,))
    assert backup.ensure_v1_upgrade_backup(database) is None
    assert not list(tmp_path.glob("*.zip"))
    assert not (root / backup.MARKER).exists()


@pytest.mark.parametrize("completed", [False, True])
def test_empty_or_completed_database_does_not_require_parent_lock(tmp_path, monkeypatch, completed):
    root = tmp_path / "data"
    root.mkdir()
    path = root / "my_database.db"
    with closing(sqlite3.connect(path)) as connection:
        if completed:
            connection.execute("CREATE TABLE migratehistory (name TEXT)")
            connection.execute("INSERT INTO migratehistory VALUES (?)", (backup.MIGRATION,))
            connection.execute("CREATE TABLE message (content TEXT)")
            connection.commit()
    def forbidden_lock(*args, **kwargs):
        pytest.fail("Skipped backups must not require a writable parent or acquire a lock")
    monkeypatch.setattr(backup, "_lock", forbidden_lock)
    assert backup.ensure_v1_upgrade_backup(SqliteDatabase(path)) is None
    assert set(tmp_path.iterdir()) == {root}
    assert not (root / backup.MARKER).exists()


def test_backup_need_is_rechecked_after_acquiring_lock(tmp_path, monkeypatch):
    root, database = old_database(tmp_path)
    original_lock = backup._lock
    from contextlib import contextmanager
    @contextmanager
    def migrate_while_waiting(path):
        with original_lock(path):
            with closing(sqlite3.connect(database.database)) as connection:
                connection.execute("CREATE TABLE migratehistory (name TEXT)")
                connection.execute("INSERT INTO migratehistory VALUES (?)", (backup.MIGRATION,))
                connection.commit()
            yield
    monkeypatch.setattr(backup, "_lock", migrate_while_waiting)
    assert backup.ensure_v1_upgrade_backup(database) is None
    assert not list(tmp_path.glob("*.zip"))
    assert not (root / backup.MARKER).exists()


def test_default_backs_up_business_schema_without_conversations(tmp_path):
    root, database = old_database(tmp_path, legacy=False)
    assert backup.ensure_v1_upgrade_backup(database, legacy_only=True) is None
    assert backup.ensure_v1_upgrade_backup(database).is_file()


@pytest.mark.parametrize("schema", [
    "CREATE TABLE agent (id INTEGER)",
    "CREATE TABLE conversation (id INTEGER)",
    "CREATE TABLE message (id INTEGER)",
    "CREATE TABLE chatdraft (id INTEGER)",
    "CREATE TABLE workflowrunrecord (source_message TEXT)",
])
def test_legacy_hook_detects_real_schema(tmp_path, schema):
    root, database = old_database(tmp_path, legacy=False)
    with sqlite3.connect(database.database) as connection:
        connection.execute(schema)
    assert backup.ensure_v1_upgrade_backup(database, legacy_only=True).is_file()


def test_live_wal_commits_restored_for_each_database(tmp_path):
    root, database = old_database(tmp_path)
    writers = []
    try:
        for path in (Path(database.database), root / "knowledge.sqlite"):
            connection = sqlite3.connect(path)
            writers.append(connection)
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA wal_autocheckpoint=0")
            connection.execute("CREATE TABLE wal_rows (text TEXT)")
            connection.execute("INSERT INTO wal_rows VALUES ('committed WAL row')")
            connection.commit()
            assert Path(str(path) + "-wal").stat().st_size > 0
        result = backup.ensure_v1_upgrade_backup(database)
        with zipfile.ZipFile(result) as archive:
            assert not any(name.endswith(("-wal", "-shm", "-journal")) for name in archive.namelist())
            archive.extractall(tmp_path / "restore")
        for path in ("my_database.db", "knowledge.sqlite"):
            with sqlite3.connect(tmp_path / "restore" / root.name / path) as connection:
                assert connection.execute("SELECT * FROM wal_rows").fetchall() == [("committed WAL row",)]
        with sqlite3.connect(tmp_path / "restore" / root.name / "my_database.db") as connection:
            assert connection.execute("SELECT * FROM message").fetchall() == [("synthetic chat",)]
    finally:
        for connection in writers:
            connection.close()


@pytest.mark.parametrize("damage", ["marker_json", "marker_path", "marker_hash", "zip_missing", "zip_corrupt"])
def test_damaged_backup_never_counts_as_success(tmp_path, damage):
    root, database = old_database(tmp_path)
    first = backup.ensure_v1_upgrade_backup(database)
    marker = root / backup.MARKER
    saved = json.loads(marker.read_text())
    if damage == "marker_json":
        marker.write_text("{broken")
    elif damage == "marker_path":
        saved["backup"] = "../outside.zip"
        marker.write_text(json.dumps(saved))
    elif damage == "marker_hash":
        saved["sha256"] = "0" * 64
        marker.write_text(json.dumps(saved))
    elif damage == "zip_missing":
        first.unlink()
    else:
        first.write_bytes(b"broken zip")
    second = backup.ensure_v1_upgrade_backup(database)
    assert second != first
    assert second.is_file()
    backup._verify(second)
    assert backup.ensure_v1_upgrade_backup(database) == second


@pytest.mark.parametrize("failure", ["zip", "snapshot", "fsync", "publish"])
def test_failure_preserves_source_and_creates_no_marker(tmp_path, monkeypatch, failure):
    root, database = old_database(tmp_path)
    attachment = root / "attachment.txt"
    attachment.write_bytes(b"synthetic private content")
    original = {p.name: p.read_bytes() for p in root.iterdir()}
    def fail(*args, **kwargs):
        raise OSError("synthetic secret must not appear")
    if failure == "zip":
        monkeypatch.setattr(backup.shutil, "copyfileobj", fail)
    elif failure == "snapshot":
        monkeypatch.setattr(backup, "_snapshot", fail)
    elif failure == "fsync":
        monkeypatch.setattr(backup.os, "fsync", fail)
    else:
        monkeypatch.setattr(backup, "_publish", fail)
    with pytest.raises(backup.UpgradeBackupError) as error:
        backup.ensure_v1_upgrade_backup(database)
    assert "synthetic secret" not in str(error.value)
    assert original == {p.name: p.read_bytes() for p in root.iterdir()}
    assert not list(tmp_path.glob("*.zip"))
    assert not list(tmp_path.glob(".v1-backup-*"))


def test_source_change_aborts(tmp_path, monkeypatch):
    root, database = old_database(tmp_path)
    attachment = root / "attachment"
    attachment.write_bytes(b"before")
    original = backup.shutil.copyfileobj
    def mutate(source, target, length):
        original(source, target, length)
        attachment.write_bytes(b"changed after streaming")
    monkeypatch.setattr(backup.shutil, "copyfileobj", mutate)
    with pytest.raises(backup.UpgradeBackupError):
        backup.ensure_v1_upgrade_backup(database)
    assert not (root / backup.MARKER).exists()
    assert not list(tmp_path.glob("*.zip"))


@pytest.mark.parametrize("location", ["file", "directory", "root", "marker"])
def test_symlinks_rejected(tmp_path, location):
    root, database = old_database(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "file").write_bytes(b"outside must not be read")
    try:
        if location == "root":
            alias = tmp_path / "alias"
            alias.symlink_to(root, target_is_directory=True)
            database = SqliteDatabase(alias / "my_database.db")
        elif location == "directory":
            (root / "link").symlink_to(outside, target_is_directory=True)
        else:
            (root / (backup.MARKER if location == "marker" else "link")).symlink_to(outside / "file")
    except OSError:
        pytest.skip("Host does not permit symlink creation")
    with pytest.raises(backup.UpgradeBackupError):
        backup.ensure_v1_upgrade_backup(database)
    assert not list(tmp_path.glob("*.zip"))


def test_concurrent_processes_reuse_one_archive(tmp_path):
    root, database = old_database(tmp_path)
    with ProcessPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run_backup, str(database.database)) for _ in range(2)]
        results = [future.result(timeout=45) for future in futures]
    assert results[0] == results[1]
    assert len(list(tmp_path.glob("*.zip"))) == 1


def test_busy_sqlite_has_bounded_timeout(tmp_path, monkeypatch):
    root, database = old_database(tmp_path)
    monkeypatch.setattr(backup, "TIMEOUT", 0.1)
    with sqlite3.connect(database.database) as connection:
        connection.execute("BEGIN EXCLUSIVE")
        with pytest.raises(backup.UpgradeBackupError):
            backup.ensure_v1_upgrade_backup(database)
    assert not (root / backup.MARKER).exists()


@pytest.mark.parametrize("wal", [False, True])
def test_retry_after_old_app_writes_creates_fresh_recovery_zip(tmp_path, wal):
    root, database = old_database(tmp_path)
    with closing(sqlite3.connect(database.database)) as writer:
        if wal:
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("PRAGMA wal_autocheckpoint=0")
        first = backup.ensure_v1_upgrade_backup(database)
        first_hash = backup._hash(first)
        writer.execute("INSERT INTO message VALUES ('new chat after failed migration')")
        writer.commit()
        (root / "new-attachment.txt").write_bytes(b"new synthetic attachment")
        second = backup.ensure_v1_upgrade_backup(database)
        assert second != first
        assert backup._hash(first) == first_hash
        with zipfile.ZipFile(second) as archive:
            assert archive.read(f"{root.name}/new-attachment.txt") == b"new synthetic attachment"
            archive.extractall(tmp_path / "retry-restore")
        with closing(sqlite3.connect(tmp_path / "retry-restore" / root.name / "my_database.db")) as restored:
            assert restored.execute("SELECT * FROM message").fetchall() == [
                ("synthetic chat",), ("new chat after failed migration",),
            ]
        assert backup.ensure_v1_upgrade_backup(database) == second


def test_attachment_only_change_invalidates_marker(tmp_path):
    root, database = old_database(tmp_path)
    attachment = root / "persistent-shm"
    attachment.write_bytes(b"first")
    first = backup.ensure_v1_upgrade_backup(database)
    attachment.write_bytes(b"second")
    second = backup.ensure_v1_upgrade_backup(database)
    assert first != second
    with zipfile.ZipFile(second) as archive:
        assert archive.read(f"{root.name}/persistent-shm") == b"second"


def test_real_fresh_migrations_001_through_005_skip_legacy_hook(tmp_path):
    from peewee_migrate import Router
    root = tmp_path / "fresh"
    root.mkdir()
    database = SqliteDatabase(root / "my_database.db")
    try:
        Router(database, migrate_dir=Path(__file__).resolve().parents[1] / "migrations").run(
            "005_add_workflow_version"
        )
        assert backup.ensure_v1_upgrade_backup(database, legacy_only=True) is None
        assert not list(tmp_path.glob("*.zip"))
    finally:
        database.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction/reparse test")
def test_windows_junction_is_rejected_without_reading_target(tmp_path):
    root, database = old_database(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "never-read").write_bytes(b"outside")
    junction = root / "junction"
    subprocess.run(
        ["cmd.exe", "/c", "mklink", "/J", str(junction), str(outside)],
        check=True, capture_output=True,
    )
    assert junction.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
    with pytest.raises(backup.UpgradeBackupError, match="reparse"):
        backup.ensure_v1_upgrade_backup(database)
    assert not list(tmp_path.glob("*.zip"))


def test_archive_target_never_overwrites_existing_path(tmp_path, monkeypatch):
    root, database = old_database(tmp_path)
    original = backup._publish
    occupied = []
    def race(source, target):
        Path(target).write_bytes(b"preexisting archive must survive")
        occupied.append(Path(target))
        original(source, target)
    monkeypatch.setattr(backup, "_publish", race)
    with pytest.raises(backup.UpgradeBackupError):
        backup.ensure_v1_upgrade_backup(database)
    assert occupied[0].read_bytes() == b"preexisting archive must survive"
    assert not (root / backup.MARKER).exists()


def test_corrupt_sqlite_snapshot_fails_integrity_check(tmp_path):
    root, database = old_database(tmp_path)
    broken = root / "broken.sqlite"
    broken.write_bytes(b"SQLite format 3\0" + b"\0" * 1024)
    with pytest.raises(backup.UpgradeBackupError):
        backup.ensure_v1_upgrade_backup(database)
    assert not (root / backup.MARKER).exists()
    assert not list(tmp_path.glob("*.zip"))


def test_missing_data_directory_is_fresh_without_creating_it(tmp_path):
    database = SqliteDatabase(tmp_path / "not-created" / "my_database.db")
    assert backup.ensure_v1_upgrade_backup(database) is None
    assert list(tmp_path.iterdir()) == []


def test_filesystem_root_is_rejected_before_any_io(tmp_path, monkeypatch):
    database = SqliteDatabase(Path(tmp_path.anchor) / "nonexistent-test.db")
    def unexpected_io(*args, **kwargs):
        pytest.fail("Root data path must be rejected before any filesystem I/O")
    monkeypatch.setattr(backup, "_ancestors", unexpected_io)
    monkeypatch.setattr(backup, "_lock", unexpected_io)
    monkeypatch.setattr(backup, "_inventory", unexpected_io)
    monkeypatch.setattr(Path, "exists", unexpected_io)
    monkeypatch.setattr(backup.os, "open", unexpected_io)
    monkeypatch.setattr(backup.os, "mkdir", unexpected_io)
    with pytest.raises(backup.UpgradeBackupError, match="drive or filesystem root"):
        backup.ensure_v1_upgrade_backup(database)


def test_private_permissions_are_set_before_archive_and_marker_publication(tmp_path, monkeypatch):
    root, database = old_database(tmp_path)
    original_chmod = backup.os.chmod
    original_publish = backup._publish
    original_replace = backup.os.replace
    restricted = set()
    def restrict(path, mode):
        assert mode == 0o600
        original_chmod(path, mode)
        restricted.add(Path(path))
    def publish(partial, final):
        assert Path(partial) in restricted
        if os.name == "posix":
            assert stat.S_IMODE(Path(partial).stat().st_mode) == 0o600
        original_publish(partial, final)
    def replace(source, target):
        assert Path(source) in restricted
        if os.name == "posix":
            assert stat.S_IMODE(Path(source).stat().st_mode) == 0o600
        original_replace(source, target)
    monkeypatch.setattr(backup.os, "chmod", restrict)
    monkeypatch.setattr(backup, "_publish", publish)
    monkeypatch.setattr(backup.os, "replace", replace)
    result = backup.ensure_v1_upgrade_backup(database)
    assert len(restricted) == 2
    if os.name == "posix":
        assert stat.S_IMODE(result.stat().st_mode) == 0o600
        assert stat.S_IMODE((root / backup.MARKER).stat().st_mode) == 0o600


@pytest.mark.parametrize("absolute", [False, True])
def test_workspace_wrapper_reads_config_without_application_imports(tmp_path, monkeypatch, absolute):
    import builtins
    root, database = old_database(tmp_path, name="custom workspace")
    config_path = tmp_path / "config.json"
    original = json.dumps({"data_path": str(root) if absolute else root.name, "other": "synthetic"})
    config_path.write_text(original, encoding="utf-8")
    original_import = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        if name == "models" or name.startswith(("models.", "utilities.config")):
            pytest.fail("Workspace preflight imported application state")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    result = backup.ensure_workspace_v1_upgrade_backup(tmp_path)
    assert result.parent == tmp_path
    assert config_path.read_text(encoding="utf-8") == original
    with zipfile.ZipFile(result) as archive:
        assert f"{root.name}/my_database.db" in archive.namelist()


def test_workspace_wrapper_defaults_to_cwd_and_does_not_initialize_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert backup.ensure_workspace_v1_upgrade_backup() is None
    assert not (tmp_path / "config.json").exists()
    assert not (tmp_path / "data").exists()
    old_database(tmp_path, name="data")
    assert backup.ensure_workspace_v1_upgrade_backup().is_file()


@pytest.mark.parametrize("text", ["{broken", "[]", '{"data_path": null}', '{"data_path": ""}'])
def test_workspace_wrapper_bad_config_is_failclosed_and_unchanged(tmp_path, text):
    config_path = tmp_path / "config.json"
    config_path.write_text(text, encoding="utf-8")
    with pytest.raises(backup.UpgradeBackupError, match="workspace data location"):
        backup.ensure_workspace_v1_upgrade_backup(tmp_path)
    assert config_path.read_text(encoding="utf-8") == text
    assert not list(tmp_path.glob("*.zip"))


def test_checkpointed_wal_database_does_not_create_source_sidecars(tmp_path):
    from diskcache import Cache
    root, database = old_database(tmp_path)
    with Cache(root / "cache") as cache:
        cache.set("synthetic", "synthetic value")
    original = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result = backup.ensure_v1_upgrade_backup(database)
    after = {p.relative_to(root): p.read_bytes() for p in root.rglob("*")
             if p.is_file() and p.name != backup.MARKER}
    assert after == original
    with zipfile.ZipFile(result) as archive:
        archive.extractall(tmp_path / "cache-restore")
    with Cache(tmp_path / "cache-restore" / root.name / "cache") as restored:
        assert restored["synthetic"] == "synthetic value"


def test_same_size_content_change_with_restored_mtime_invalidates_marker(tmp_path):
    root, database = old_database(tmp_path)
    attachment = root / "attachment"
    attachment.write_bytes(b"first")
    original_stat = attachment.stat()
    first = backup.ensure_v1_upgrade_backup(database)
    attachment.write_bytes(b"other")
    os.utime(attachment, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    second = backup.ensure_v1_upgrade_backup(database)
    assert second != first
    with zipfile.ZipFile(second) as archive:
        assert archive.read(f"{root.name}/attachment") == b"other"


def test_online_backup_busy_callback_expires(tmp_path, monkeypatch):
    root, database = old_database(tmp_path)
    monkeypatch.setattr(backup, "TIMEOUT", 0.1)
    with closing(sqlite3.connect(database.database)) as connection:
        connection.execute("BEGIN EXCLUSIVE")
        with pytest.raises(backup.UpgradeBackupError, match="timed out"):
            backup._snapshot(Path(database.database), tmp_path / "snapshot.db")
    assert not (root / backup.MARKER).exists()


def test_lock_timeout_is_bounded(tmp_path, monkeypatch):
    root, database = old_database(tmp_path)
    monkeypatch.setattr(backup, "TIMEOUT", 0.05)
    def busy(*args):
        raise OSError("busy synthetic lock")
    if os.name == "nt":
        import msvcrt
        monkeypatch.setattr(msvcrt, "locking", busy)
    else:
        import fcntl
        monkeypatch.setattr(fcntl, "flock", busy)
    with pytest.raises(backup.UpgradeBackupError, match="lock timed out"):
        backup.ensure_v1_upgrade_backup(database)
    assert not (root / backup.MARKER).exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows rename no-replace semantics")
def test_windows_without_hardlinks_can_publish_backup(tmp_path, monkeypatch):
    root, database = old_database(tmp_path)
    def no_hardlinks(*args, **kwargs):
        raise OSError("Filesystem does not support hard links")
    monkeypatch.setattr(backup.os, "link", no_hardlinks)
    result = backup.ensure_v1_upgrade_backup(database)
    assert result.is_file()
    backup._verify(result)
    assert backup.ensure_v1_upgrade_backup(database) == result


@pytest.mark.skipif(os.name != "nt", reason="Windows rename no-replace semantics")
def test_windows_rename_refuses_existing_destination_without_hardlinks(tmp_path, monkeypatch):
    partial = tmp_path / "test.partial"
    final = tmp_path / "existing.zip"
    partial.write_bytes(b"new archive")
    final.write_bytes(b"existing archive")
    def no_hardlinks(*args, **kwargs):
        raise OSError("Filesystem does not support hard links")
    monkeypatch.setattr(backup.os, "link", no_hardlinks)
    with pytest.raises(FileExistsError):
        backup._publish(partial, final)
    assert final.read_bytes() == b"existing archive"
    assert partial.read_bytes() == b"new archive"
