from __future__ import annotations

import math
import json
import sqlite3
import stat
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from knowledge_base import KnowledgeError, KnowledgeService
from knowledge_base.storage import selected_metadata


class Embedder:
    def get(self, value):
        def vector(text):
            text = text.casefold()
            return [1.0 + text.count("apple"), 1.0 + text.count("banana"), 1.0 + text.count("中文")]
        return vector(value) if isinstance(value, str) else [vector(text) for text in value]


@pytest.fixture
def service(tmp_path):
    instance = KnowledgeService(tmp_path / "knowledge-base", embedder_factory=lambda base: Embedder(),
                                extractor=lambda path: path.read_text(encoding="utf-8"), start_worker=False)
    yield instance
    instance.close()


def base(service, name="Notes"):
    return service.dispatch("create", {"name": name, "embedding_provider": "test", "embedding_model": "test",
                                       "embedding_dimensions": 3, "chunk_size": 64, "chunk_overlap": 8})


def text(service, kb, name="Note", value="apple 中文资料"):
    return service.dispatch("add_text", {"kb_id": kb["id"], "name": name, "text": value})


def test_real_qdrant_publication_scope_chinese_and_restart(service):
    first, second = base(service), base(service, "Other")
    one = text(service, first)
    other = text(service, second, value="apple apple apple banana")
    assert service.search([first["id"]], "apple")["results"] == []
    assert service.run_pending() == 2
    for mode in ("keyword", "semantic", "hybrid"):
        hits = service.search([first["id"]], "apple", mode=mode)["results"]
        assert hits and {hit["document_id"] for hit in hits} == {one["id"]}
        assert all(hit["document_id"] != other["id"] for hit in hits)
    for query in ("中文", "中文资料"):
        assert service.search([first["id"]], query, mode="keyword")["results"]
    root = service.root
    service.close()
    reopened = KnowledgeService(root, embedder_factory=lambda base: Embedder(), start_worker=False)
    try:
        assert reopened.search([first["id"]], "apple", mode="semantic")["results"][0]["document_id"] == one["id"]
        assert reopened.read_document([first["id"]], one["id"], offset=1, limit=4)["text"] == "pple"
        with pytest.raises(KnowledgeError, match="not available"):
            reopened.read_document([second["id"]], one["id"])
        assert (root / "vectors").is_dir()
    finally:
        reopened.close()


def test_hierarchy_move_cycles_versions_and_scope_before_topk(service):
    kb, other = base(service), base(service, "Other")
    folder = service.create_folder(kb["id"], "Folder")
    nested = service.create_folder(kb["id"], "Nested", folder["id"])
    inside = service.add_text(kb["id"], "Inside", "banana", nested["id"])
    service.add_text(kb["id"], "Outside", "apple apple apple")
    service.run_pending()
    assert service.items(kb["id"])["total"] == 2
    assert service.items(kb["id"], folder["id"], search="Inside")["items"][0]["path"] == "Folder/Nested/Inside"
    assert service.tree(kb["id"])["folders"][0]["children"][0]["id"] == nested["id"]
    hit = service.search([kb["id"]], "apple", mode="semantic", folder_id=folder["id"], limit=1)["results"][0]
    assert hit["document_id"] == inside["id"]
    with pytest.raises(KnowledgeError, match="inside itself"):
        service.move(kb["id"], folder["id"], folder["updated_at"], nested["id"])
    with pytest.raises(KnowledgeError):
        service.move(other["id"], inside["id"], inside["updated_at"])
    with pytest.raises(KnowledgeError, match="changed"):
        service.rename(kb["id"], folder["id"], "Changed", "old")
    renamed = service.rename(kb["id"], folder["id"], "Renamed", folder["updated_at"])
    assert service.get_item(kb["id"], nested["id"])["path"] == "Renamed/Nested"
    moved = service.move(kb["id"], nested["id"], nested["updated_at"])
    assert moved["path"] == "Nested"
    service.delete_item(kb["id"], renamed["id"], renamed["updated_at"])
    assert service.get_item(kb["id"], inside["id"])


def test_directory_import_managed_copy_limits_and_preview(service, tmp_path):
    kb = base(service)
    source = tmp_path / "input"
    source.mkdir()
    (source / "中文.txt").write_text("中文 apple", encoding="utf-8")
    (source / "binary.exe").write_bytes(b"\x00")
    nested = source / "nested"
    nested.mkdir()
    (nested / "note.md").write_text("banana", encoding="utf-8")
    result = service.import_directory(kb["id"], str(source))
    assert len(result["items"]) == 4
    assert result["skipped"] == [{"name": "binary.exe", "error_code": "unsupported_type"}]
    assert len(list(service.originals.iterdir())) == 2
    service.run_pending()
    document = next(item for item in result["items"] if item["name"] == "中文.txt")
    assert service.preview(kb["id"], document["id"])["text"] == "中文 apple"
    (source / "中文.txt").write_text("modified original", encoding="utf-8")
    service.reindex(kb["id"], document["id"])
    service.run_pending()
    assert service.preview(kb["id"], document["id"])["text"] == "中文 apple"
    item = service.get_item(kb["id"], document["id"])
    service.delete_item(kb["id"], item["id"], item["updated_at"])
    assert (source / "中文.txt").read_text(encoding="utf-8") == "modified original"
    assert len(list(service.originals.iterdir())) == 1
    assert service.import_files(kb["id"], ["relative.txt"])["skipped"][0]["error_code"] == "unsafe_path"
    assert service.import_files(kb["id"], [str(service.originals / "missing.txt")])["skipped"]


def test_symlink_and_junction_rejection(service, tmp_path):
    kb = base(service)
    original = tmp_path / "original.txt"
    original.write_text("apple", encoding="utf-8")
    linked = tmp_path / "linked.txt"
    try:
        linked.symlink_to(original)
    except OSError:
        pytest.skip("Creating symlinks requires Windows developer mode.")
    assert service.import_files(kb["id"], [str(linked)])["skipped"] == [
        {"name": "linked.txt", "error_code": "unsafe_path"}]


@pytest.mark.parametrize("bad", [[[math.nan, 0, 1]], [[math.inf, 0, 1]], [[1e308, 0, 1]], [[1, 2]], [], [[1, 2, 3], [1, 2, 3]]])
def test_invalid_embeddings_fail_without_publication_and_retry(service, bad):
    kb = base(service)
    item = text(service, kb)
    class Bad:
        def get(self, value):
            return bad
    service.embedder_factory = lambda base: Bad()
    service.run_pending()
    failed = service.get_item(kb["id"], item["id"])
    assert failed["status"] == "failed"
    assert failed["error_code"] == "invalid_embedding"
    assert service.search([kb["id"]], "apple", mode="keyword")["results"]
    assert service.search([kb["id"]], "apple", mode="semantic")["warnings"][0]["error_code"] == "index_incomplete"
    assert service.preview(kb["id"], item["id"])["text"]
    service.embedder_factory = lambda base: Embedder()
    service.reindex(kb["id"], item["id"])
    service.run_pending()
    assert service.get_item(kb["id"], item["id"])["status"] == "ready"
    assert service.search([kb["id"]], "apple")["results"]


def test_durable_running_job_recovers_on_restart(service):
    kb = base(service)
    item = text(service, kb)
    service._db.execute("UPDATE jobs SET status='running',phase='embedding'")
    service._db.execute("UPDATE items SET status='indexing'")
    root = service.root
    service.close()
    restarted = KnowledgeService(root, embedder_factory=lambda base: Embedder(), start_worker=False)
    try:
        assert restarted.get_item(kb["id"], item["id"])["status"] == "queued"
        restarted.run_pending()
        assert restarted.get_item(kb["id"], item["id"])["status"] == "ready"
    finally:
        restarted.close()


def test_delete_and_reindex_during_embedding_cannot_publish_stale_generation(tmp_path):
    entered, release = threading.Event(), threading.Event()
    calls = []
    class Slow(Embedder):
        def get(self, value):
            calls.append(value)
            if len(calls) == 1:
                entered.set()
                assert release.wait(10)
            return super().get(value)
    service = KnowledgeService(tmp_path / "kb", embedder_factory=lambda base: Slow(), start_worker=False)
    kb = base(service)
    one, removed = text(service, kb), text(service, kb, "Removed")
    worker = threading.Thread(target=service.run_pending)
    worker.start()
    try:
        assert entered.wait(5)
        service.reindex(kb["id"], one["id"])
        service.delete_item(kb["id"], removed["id"], removed["updated_at"])
        release.set()
        worker.join(10)
        assert not worker.is_alive()
        assert service.get_item(kb["id"], one["id"])["status"] == "ready"
        assert {hit["document_id"] for hit in service.search([kb["id"]], "apple")["results"]} == {one["id"]}
        jobs = service._db.execute("SELECT status FROM jobs WHERE document_id=? ORDER BY created_at", (one["id"],)).fetchall()
        assert [row[0] for row in jobs] == ["cancelled", "completed"]
    finally:
        release.set()
        worker.join(10)
        service.close()


def test_selected_bases_is_metadata_only_and_rejects_duplicates(service, monkeypatch):
    kb = base(service)
    def forbidden(*args, **kwargs):
        pytest.fail("Metadata validation must never open Qdrant or create an owner.")
    monkeypatch.setattr(service.vectors, "_client", forbidden)
    assert selected_metadata(service.root, [kb["id"]]) == [{"kb_id": kb["id"], "name": kb["name"]}]
    assert not service.root.joinpath("vectors").exists()
    with pytest.raises(KnowledgeError):
        selected_metadata(service.root, [kb["id"], kb["id"]])
    with pytest.raises(KnowledgeError):
        selected_metadata(service.root, [uuid4().hex])


def test_provider_errors_are_safe_and_do_not_publish(service):
    kb = base(service)
    item = text(service, kb)
    def broken(base):
        raise RuntimeError("SECRET provider token")
    service.embedder_factory = broken
    service.run_pending()
    result = service.get_item(kb["id"], item["id"])
    assert result["status"] == "failed"
    assert "SECRET" not in str(result)
    assert "SECRET" not in str(service.search([kb["id"]], "apple"))


def test_legacy_migration_keeps_ids_text_unindexed_and_never_resurrects(tmp_path):
    path = tmp_path / "legacy.sqlite"
    kb_id, document_id = uuid4().hex, uuid4().hex
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE user_vector_database(id INTEGER,vid TEXT,name TEXT,embedding_provider TEXT,embedding_model TEXT,embedding_size INTEGER);
        CREATE TABLE user_object(oid TEXT,title TEXT,vector_database_id INTEGER,raw_data TEXT,source_url TEXT);
    """)
    db.execute("INSERT INTO user_vector_database VALUES(1,?,'Legacy','test','test',3)", (kb_id,))
    db.execute("INSERT INTO user_object VALUES(?,'Document',1,?,?)",
               (document_id, '{"text":"recovered 中文 apple","file":"NEVER_OPEN_ORIGINAL"}', "https://example.test"))
    db.commit()
    db.close()
    def forbidden(base):
        pytest.fail("Migration must not call an embedding provider.")
    root = tmp_path / "kb"
    service = KnowledgeService(root, embedder_factory=forbidden, legacy_path=path, start_worker=False)
    try:
        item = service.get_item(kb_id, document_id)
        assert item["status"] == "unindexed"
        assert service.read_document([kb_id], document_id)["text"] == "recovered 中文 apple"
        assert service.search([kb_id], "中文", mode="keyword")["results"]
        assert service.run_pending() == 0
        service.delete_item(kb_id, document_id, item["updated_at"])
    finally:
        service.close()
    repeated = KnowledgeService(root, embedder_factory=forbidden, legacy_path=path, start_worker=False)
    try:
        assert repeated.items(kb_id)["total"] == 0
        record = repeated.get(kb_id)
        repeated.delete(kb_id, record["updated_at"])
    finally:
        repeated.close()
    final = KnowledgeService(root, embedder_factory=forbidden, legacy_path=path, start_worker=False)
    try:
        assert final.list() == {"bases": []}
    finally:
        final.close()
    db = sqlite3.connect(path)
    assert db.execute("SELECT count(*) FROM user_object").fetchone()[0] == 1
    db.close()


def test_background_start_stop_and_source_url(tmp_path):
    service = KnowledgeService(tmp_path / "kb", embedder_factory=lambda base: Embedder(), start_worker=False)
    kb = base(service)
    item = service.add_text(kb["id"], "From web", "apple", source_url="https://example.test")
    assert item["source_url"] == "https://example.test"
    service.start()
    service.start()
    service.wait_idle()
    assert service.get_item(kb["id"], item["id"])["status"] == "ready"
    service.stop()
    service.stop()
    assert service._closed


def test_partial_vector_write_remains_hidden_and_retry_reclaims_stale_points(service, monkeypatch):
    kb = base(service)
    item = text(service, kb, value="apple 中文 banana. " * 180)
    original_write = service.vectors.write
    writes = []
    def fail_second(*args):
        writes.append(args)
        if len(writes) == 2:
            raise RuntimeError("SECRET simulated disk failure")
        return original_write(*args)
    monkeypatch.setattr(service.vectors, "write", fail_second)
    service.run_pending()
    assert service.get_item(kb["id"], item["id"])["status"] == "failed"
    assert service.search([kb["id"]], "apple", mode="keyword")["results"]
    assert service.search([kb["id"]], "apple", mode="semantic")["results"] == []
    monkeypatch.setattr(service.vectors, "write", original_write)
    service.reindex(kb["id"], item["id"])
    service.run_pending()
    active = service._item(kb["id"], item["id"])["active_token"]
    points, _ = service.vectors._client().scroll(service.vectors.collection(kb["id"]), limit=1000)
    assert points and {point.payload["token"] for point in points} == {active}
    assert service.search([kb["id"]], "apple")["results"]


def test_dimension_change_between_batches_never_publishes(service):
    kb = base(service)
    item = text(service, kb, value="apple banana 中文. " * 180)
    class Changing(Embedder):
        calls = 0
        def get(self, value):
            self.calls += 1
            return [[1, 2, 3] if self.calls == 1 else [1, 2] for _ in value]
    embedder = Changing()
    service.embedder_factory = lambda base: embedder
    service.run_pending()
    result = service.get_item(kb["id"], item["id"])
    assert result["status"] == "failed" and result["error_code"] == "invalid_embedding"
    assert service.search([kb["id"]], "apple", mode="keyword")["results"]


def test_reindex_and_delete_after_vector_call_cannot_return_stale_hit(service):
    kb = base(service)
    item = text(service, kb)
    service.run_pending()
    class ReindexOnQuery(Embedder):
        def get(self, value):
            if isinstance(value, str):
                service.reindex(kb["id"], item["id"])
            return super().get(value)
    service.embedder_factory = lambda base: ReindexOnQuery()
    assert service.search([kb["id"]], "apple")["results"] == []


def test_metadata_function_never_constructs_singleton(service, monkeypatch):
    import knowledge_base
    kb = base(service)
    monkeypatch.setattr(knowledge_base, "_root", lambda: service.root)
    monkeypatch.setattr(knowledge_base, "knowledge_service", lambda: pytest.fail("Owner must not be created."))
    assert knowledge_base.selected_bases([kb["id"]]) == [{"kb_id": kb["id"], "name": kb["name"]}]
    assert knowledge_base.selected_bases([]) == []


def test_api_safe_errors(service, monkeypatch):
    from api import knowledge_base_api
    monkeypatch.setattr(knowledge_base_api, "knowledge_service", lambda: service)
    api = knowledge_base_api.KnowledgeBaseAPI()
    assert api.list({})["data"] == {"bases": []}
    response = api.create({"name": "../bad"})
    assert response["status"] == 400
    assert response["data"]["error_code"] == "invalid_input"
    def broken(*args):
        raise RuntimeError("SECRET provider token")
    monkeypatch.setattr(service, "dispatch", broken)
    assert "SECRET" not in str(api.list({}))


def test_failed_embeddings_keep_lexical_evidence_and_warn(service):
    kb = base(service)
    item = text(service, kb)
    service.embedder_factory = lambda base: (_ for _ in ()).throw(RuntimeError("SECRET"))
    service.run_pending()
    keyword = service.search([kb["id"]], "中文", mode="keyword")
    assert keyword["results"][0]["document_id"] == item["id"]
    semantic = service.search([kb["id"]], "中文", mode="semantic")
    assert semantic["results"] == []
    assert semantic["warnings"][0]["error_code"] == "index_incomplete"
    assert service.preview(kb["id"], item["id"])["text"]
    assert "SECRET" not in str(semantic)


def test_search_sql_limits_text_reads_to_scoped_candidates(service):
    kb, unrelated = base(service), base(service, "Unrelated")
    document = text(service, kb)
    for index in range(5):
        text(service, unrelated, name=f"Other {index}", value="apple apple apple " * 100)
    service.run_pending()
    queries = []
    service._db.set_trace_callback(queries.append)
    try:
        assert service.search([kb["id"]], "apple", mode="semantic", limit=1)["results"][0]["document_id"] == document["id"]
        assert service.search([kb["id"]], "apple", mode="keyword", limit=1)["results"][0]["document_id"] == document["id"]
    finally:
        service._db.set_trace_callback(None)
    chunk_reads = [query for query in queries if query.startswith("SELECT c.* FROM chunks")]
    assert chunk_reads and all("c.id=" in query and "i.kb_id IN" in query for query in chunk_reads)
    assert not any(query.startswith("SELECT * FROM chunks") for query in queries)
    fts = next(query for query in queries if "chunk_fts MATCH" in query)
    assert "i.kb_id IN" in fts and "LIMIT 4" in fts


def test_add_text_has_managed_original_without_native_window(service):
    kb = base(service)
    opened = []
    service.opener = opened.append
    document = text(service, kb)
    service.open_file(kb["id"], document["id"])
    assert len(opened) == 1
    assert opened[0].parent == service.originals
    assert opened[0].read_text(encoding="utf-8") == "apple 中文资料"


def test_legacy_original_is_copied_not_moved(tmp_path):
    source = tmp_path / "old.txt"
    source.write_text("original bytes", encoding="utf-8")
    legacy = tmp_path / "legacy.sqlite"
    kb_id, document_id = uuid4().hex, uuid4().hex
    db = sqlite3.connect(legacy)
    db.executescript("""
        CREATE TABLE user_vector_database(id INTEGER,vid TEXT,name TEXT,embedding_provider TEXT,embedding_model TEXT,embedding_size INTEGER);
        CREATE TABLE user_object(oid TEXT,title TEXT,vector_database_id INTEGER,raw_data TEXT);
    """)
    db.execute("INSERT INTO user_vector_database VALUES(1,?,'Legacy','test','test',3)", (kb_id,))
    db.execute("INSERT INTO user_object VALUES(?,'Document',1,?)",
               (document_id, json.dumps({"text": "cached extraction", "file": str(source)})))
    db.commit()
    db.close()
    service = KnowledgeService(tmp_path / "kb", start_worker=False, legacy_path=legacy)
    try:
        record = service._item(kb_id, document_id)
        assert record["status"] == "unindexed"
        assert service._original(record).read_bytes() == source.read_bytes()
        assert service.read_document([kb_id], document_id)["text"] == "cached extraction"
        service.delete(kb_id, service.get(kb_id)["updated_at"])
        assert source.read_text(encoding="utf-8") == "original bytes"
    finally:
        service.close()


def test_import_entry_cap_is_global(service, tmp_path, monkeypatch):
    from knowledge_base import service as service_module
    monkeypatch.setattr(service_module, "MAX_ENTRIES", 3)
    source = tmp_path / "directory"
    for directory in ("one", "two", "three"):
        folder = source / directory
        folder.mkdir(parents=True)
        for index in range(5):
            (folder / f"{index}.txt").write_text("apple", encoding="utf-8")
    kb = base(service)
    result = service.import_directory(kb["id"], str(source))
    assert len(result["items"]) <= 4  # Synthetic imported root plus at most three source entries.
    assert sum(entry["error_code"] == "entry_limit" for entry in result["skipped"]) == 1
    assert len(list(service.originals.iterdir())) <= 3


def test_reparse_attribute_on_ancestor_is_rejected(tmp_path, monkeypatch):
    from knowledge_base.storage import safe_path
    source = tmp_path / "junction" / "file.txt"
    source.parent.mkdir()
    source.write_text("apple", encoding="utf-8")
    original_lstat = Path.lstat
    def lstat(path, *args, **kwargs):
        if path == source.parent:
            return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        return original_lstat(path, *args, **kwargs)
    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(KnowledgeError, match="junction"):
        safe_path(source)


def test_metadata_scope_has_twenty_base_limit(service):
    with pytest.raises(KnowledgeError, match="20"):
        selected_metadata(service.root, [uuid4().hex for _ in range(21)])


def test_restart_reclaims_partial_points_even_when_job_token_is_reused(service):
    kb = base(service)
    item = text(service, kb)
    job = dict(service._db.execute("SELECT * FROM jobs").fetchone())
    obsolete = {"id": uuid4().hex, "document_id": item["id"]}
    service.vectors.write(kb["id"], 3, [obsolete], [[1, 2, 3]], job["id"])
    service._db.execute("UPDATE jobs SET status='running',phase='embedding'")
    root = service.root
    service.close()
    restarted = KnowledgeService(root, embedder_factory=lambda base: Embedder(), start_worker=False)
    try:
        restarted.run_pending()
        points, _ = restarted.vectors._client().scroll(restarted.vectors.collection(kb["id"]), limit=1000)
        assert obsolete["id"] not in {str(point.id).replace("-", "") for point in points}
        assert restarted.search([kb["id"]], "apple", mode="semantic", limit=1)["results"][0]["document_id"] == item["id"]
    finally:
        restarted.close()


def test_shutdown_during_provider_call_keeps_resources_until_worker_returns(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    class Slow(Embedder):
        def get(self, value):
            entered.set()
            assert release.wait(10)
            return super().get(value)
    instance = KnowledgeService(tmp_path / "kb", embedder_factory=lambda base: Slow(), start_worker=False)
    kb = base(instance)
    item = text(instance, kb)
    instance.start()
    assert entered.wait(5)
    original_join = instance._thread.join
    monkeypatch.setattr(instance._thread, "join", lambda timeout=None: original_join(0))
    try:
        instance.close()
        assert not instance._closed
        with pytest.raises(KnowledgeError) as occupied:
            KnowledgeService(instance.root, start_worker=False)
        assert occupied.value.code == "owner_in_use"
        release.set()
        original_join(10)
        assert instance._closed
        restarted = KnowledgeService(instance.root, embedder_factory=lambda base: Embedder(), start_worker=False)
        try:
            assert restarted.get_item(kb["id"], item["id"])["status"] == "queued"
            restarted.run_pending()
            assert restarted.get_item(kb["id"], item["id"])["status"] == "ready"
        finally:
            restarted.close()
    finally:
        release.set()
        original_join(10)
        instance.close()


def test_lifetime_owner_rejects_second_service_before_recovery_and_allows_metadata(tmp_path, monkeypatch):
    from knowledge_base import service as service_module

    entered, release = threading.Event(), threading.Event()
    def extract(path):
        entered.set()
        assert release.wait(15)
        return path.read_text(encoding="utf-8")
    owner = KnowledgeService(tmp_path / "kb", extractor=extract, embedder_factory=lambda base: Embedder(),
                             start_worker=False)
    kb = base(owner)
    item = text(owner, kb)
    owner.start()
    try:
        assert entered.wait(5)
        assert owner.vectors.client is None
        before = dict(owner._db.execute("SELECT * FROM jobs WHERE document_id=?", (item["id"],)).fetchone())
        assert before["status"] == "running" and before["phase"] == "extracting"
        with monkeypatch.context() as patch:
            patch.setattr(service_module, "connect", lambda root: pytest.fail("A contender must not open SQLite."))
            with pytest.raises(KnowledgeError) as occupied:
                KnowledgeService(owner.root, start_worker=False)
            assert occupied.value.code == "owner_in_use"
        assert selected_metadata(owner.root, [kb["id"]]) == [{"kb_id": kb["id"], "name": kb["name"]}]
        probe = """
import sys
from pathlib import Path
from knowledge_base import KnowledgeError, KnowledgeService
from knowledge_base.storage import selected_metadata
root = Path(sys.argv[1])
try:
    contender = KnowledgeService(root, start_worker=False)
except KnowledgeError as error:
    assert error.code == "owner_in_use", error.code
else:
    contender.close()
    raise AssertionError("A second process acquired the active owner root.")
assert selected_metadata(root, [sys.argv[2]])[0]["kb_id"] == sys.argv[2]
"""
        child = subprocess.run([sys.executable, "-B", "-c", probe, str(owner.root), kb["id"]],
                               cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=10)
        assert child.returncode == 0, child.stderr
        after = dict(owner._db.execute("SELECT * FROM jobs WHERE document_id=?", (item["id"],)).fetchone())
        assert after == before
        assert owner.get_item(kb["id"], item["id"])["status"] == "indexing"
        assert owner.get(kb["id"])["name"] == kb["name"]
        release.set()
        owner.wait_idle()
        assert owner.get_item(kb["id"], item["id"])["status"] == "ready"
    finally:
        release.set()
        owner.close()
    next_owner = KnowledgeService(owner.root, embedder_factory=lambda base: Embedder(), start_worker=False)
    try:
        assert next_owner.get(kb["id"])["id"] == kb["id"]
    finally:
        next_owner.close()


@pytest.mark.parametrize("phase", ["schema", "migration", "start"])
def test_constructor_failure_closes_resources_and_releases_owner(tmp_path, monkeypatch, phase):
    from knowledge_base import migration, storage
    root, databases, handles = tmp_path / "kb", [], []
    with monkeypatch.context() as patch:
        if phase == "schema":
            def fail_schema(db):
                databases.append(db)
                raise RuntimeError("simulated initialization failure")
            patch.setattr(storage, "_initialize", fail_schema)
        elif phase == "migration":
            def fail_migration(service, path):
                databases.append(service._db)
                handles.append(service._owner_file)
                raise RuntimeError("simulated initialization failure")
            patch.setattr(migration, "migrate_legacy", fail_migration)
        else:
            def fail_start(service):
                databases.append(service._db)
                handles.append(service._owner_file)
                raise RuntimeError("simulated initialization failure")
            patch.setattr(KnowledgeService, "start", fail_start)
        with pytest.raises(RuntimeError, match="simulated initialization failure"):
            KnowledgeService(root, legacy_path=tmp_path / "legacy.sqlite", start_worker=phase == "start")
    for db in databases:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            db.execute("SELECT 1")
    assert all(handle.closed for handle in handles)
    owner = KnowledgeService(root, start_worker=False)
    owner.close()


def test_retrieval_warnings_aggregate_counts_per_kb_and_scope(service):
    first, second, outside = base(service), base(service, "Second"), base(service, "Outside")
    folder = service.create_folder(first["id"], "Folder")
    with service._write():
        for index in range(1500):
            service._insert_item(first["id"], folder["id"], f"Unindexed {index}", "file")
        for index in range(500):
            key = service._insert_item(first["id"], None, f"Failed {index}", "file")
            service._db.execute("UPDATE items SET status='failed' WHERE id=?", (key,))
        service._insert_item(second["id"], None, "Other unindexed", "file")
        service._insert_item(outside["id"], None, "Excluded", "file")
    result = service.search([first["id"], second["id"]], "apple", mode="semantic")
    assert len(result["warnings"]) == 2
    warnings = {warning["kb_id"]: warning for warning in result["warnings"]}
    assert warnings[first["id"]]["count"] == 2000
    assert warnings[first["id"]]["counts"] == {"unindexed": 1500, "failed": 500}
    assert warnings[first["id"]]["error_code"] == "index_incomplete"
    assert warnings[second["id"]]["count"] == 1
    assert warnings[second["id"]]["error_code"] == "unindexed"
    assert all("document_id" not in warning for warning in result["warnings"])
    narrowed = service.search([first["id"], second["id"]], "apple", mode="semantic", folder_id=folder["id"])
    assert len(narrowed["warnings"]) == 1
    assert narrowed["warnings"][0]["count"] == 1500
    assert narrowed["warnings"][0]["error_code"] == "unindexed"


def test_semantic_failure_merges_into_existing_kb_warning(service):
    kb = base(service)
    text(service, kb)
    service.run_pending()
    with service._write():
        service._insert_item(kb["id"], None, "Unindexed", "file")
    def fail(base):
        raise RuntimeError("SECRET provider failure")
    service.embedder_factory = fail
    warnings = service.search([kb["id"]], "apple", mode="semantic")["warnings"]
    assert len(warnings) == 1
    assert warnings[0]["count"] == 2
    assert warnings[0]["counts"] == {"unindexed": 1, "semantic_unavailable": 1}
    assert warnings[0]["error_code"] == "semantic_unavailable"
    assert "SECRET" not in str(warnings)
