import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from knowledge_base import KnowledgeError, KnowledgeService
from knowledge_base.query import INVALID_QUERY_MESSAGE, validate_query


class NoVectors:
    def close(self):
        pass


@pytest.fixture
def service(tmp_path):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Browse and invalid queries must never invoke providers")

    instance = KnowledgeService(tmp_path / "kb", embedder_factory=forbidden, reranker_factory=forbidden,
                                vector_store=NoVectors(), start_worker=False)
    yield instance
    assert calls == []
    instance.close()


def base(service, name="Notes"):
    return service.create(name, "test", "test", embedding_dimensions=3)


def item(service, kb, name, *, parent=None, kind="file", status="ready", active=True, chunks=1,
         stale=False, content="apple 中文 日本語 한국어 123 C++"):
    with service._write():
        key = service._insert_item(kb["id"], parent, name, kind, text="PRIVATE_FULL_TEXT", original="PRIVATE_PHYSICAL_PATH")
        token = uuid4().hex
        service._db.execute("UPDATE items SET status=?,active_token=?,chunk_count=?,error_code=? WHERE id=?",
                            (status, token if active else None, chunks, "embedding_failed" if status == "failed" else "", key))
        if kind == "file":
            service._db.executemany("INSERT INTO chunks VALUES(?,?,?,?,?)", [
                (uuid4().hex, key, "stale" if stale else token, index, content) for index in range(chunks)])
    return key


def test_empty_root_and_dispatch(service):
    kb = base(service)
    result = service.dispatch("browse", {"kb_ids": [kb["id"]]})
    assert result == {"bases": [{"kb_id": kb["id"], "name": "Notes", "document_count": 0,
                                  "keyword_documents": 0, "semantic_documents": 0, "status_counts": {}}],
                      "items": [], "total": 0, "offset": 0, "limit": 50, "next_offset": None, "truncated": False}


def test_root_nested_and_multibase_are_stable_and_direct_children_only(service):
    first, second, outside = base(service, "First"), base(service, "Second"), base(service, "Private")
    folder = service.create_folder(first["id"], "资料")
    nested = service.create_folder(first["id"], "子目录", folder["id"])
    root = item(service, first, "a.txt")
    child = item(service, first, "b.txt", parent=folder["id"])
    deep = item(service, first, "c.txt", parent=nested["id"])
    other = item(service, second, "other.txt")
    hidden = item(service, outside, "PRIVATE_NAME")
    result = service.browse([first["id"], second["id"]])
    assert result == service.browse([second["id"], first["id"]])
    assert {row["id"] for row in result["items"]} == {folder["id"], root, other}
    assert [row["kb_id"] for row in result["items"]] == sorted(row["kb_id"] for row in result["items"])
    assert all(set(row) == {"id", "kb_id", "parent_id", "kind", "name", "path", "status", "chunk_count", "error_code"}
               for row in result["items"])
    sub = service.browse([second["id"], first["id"]], folder_id=folder["id"])
    assert [row["id"] for row in sub["items"]] == [nested["id"], child]
    assert [row["path"] for row in sub["items"]] == ["资料/子目录", "资料/b.txt"]
    assert sub["bases"] == result["bases"]
    assert service.browse([first["id"]], folder_id=nested["id"])["items"][0]["id"] == deep
    assert hidden not in json.dumps(result) and "PRIVATE" not in json.dumps(result)


def test_statistics_cover_all_files_and_require_current_chunks(service):
    kb = base(service)
    folder = service.create_folder(kb["id"], "Folder")
    item(service, kb, "ready", parent=folder["id"], chunks=2)
    item(service, kb, "ready_empty", chunks=0)
    item(service, kb, "queued", status="queued", active=False, chunks=0)
    item(service, kb, "queued_extracted", status="queued")
    failed = item(service, kb, "failed_extracted", status="failed")
    item(service, kb, "stale", status="failed", stale=True)
    item(service, kb, "unindexed", status="unindexed", active=False, chunks=0)
    result = service.browse([kb["id"]], folder_id=folder["id"])
    assert result["bases"] == [{"kb_id": kb["id"], "name": "Notes", "document_count": 7,
                                "keyword_documents": 3, "semantic_documents": 1,
                                "status_counts": {"ready": 2, "queued": 2, "failed": 2, "unindexed": 1}}]
    assert result["total"] == 1
    root = service.browse([kb["id"]])
    assert next(row for row in root["items"] if row["id"] == failed)["error_code"] == "embedding_failed"


def test_browse_does_not_read_content_or_physical_path_columns(service):
    kb = base(service)
    folder = service.create_folder(kb["id"], "Folder")
    nested = service.create_folder(kb["id"], "Nested", folder["id"])
    item(service, kb, "child", parent=nested["id"])
    reads = []

    def authorize(action, table, column, *args):
        if action == sqlite3.SQLITE_READ:
            reads.append((table, column))
            if (table == "items" and column in {"extracted_text", "original", "source_url"}) or (table == "chunks" and column == "text"):
                return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    service._db.set_authorizer(authorize)
    try:
        result = service.browse([kb["id"]], folder_id=nested["id"])
        assert result["items"][0]["path"] == "Folder/Nested/child"
        assert result["bases"][0]["keyword_documents"] == 1
    finally:
        service._db.set_authorizer(None)
    assert reads


def test_paging_and_offset_ceiling_are_explicit(service):
    kb = base(service)
    with service._write():
        service._db.executemany("""INSERT INTO items(id,kb_id,kind,name,status,created_at,updated_at)
                                  VALUES(?,?,'file',?,'queued','stamp','stamp')""",
                                [(uuid4().hex, kb["id"], f"entry{index:05}") for index in range(10052)])
    first = service.browse([kb["id"]], limit=2)
    second = service.browse([kb["id"]], offset=first["next_offset"], limit=2)
    assert first["total"] == 10052 and first["next_offset"] == 2 and not first["truncated"]
    assert [row["name"] for row in first["items"] + second["items"]] == [f"entry{index:05}" for index in range(4)]
    assert service.browse([kb["id"]], offset=9950)["next_offset"] == 10000
    last = service.browse([kb["id"]], offset=10000)
    assert len(last["items"]) == 50 and last["next_offset"] is None and last["truncated"] is True
    small = base(service, "Small")
    item(service, small, "only")
    assert service.browse([small["id"]], offset=1)["items"] == []
    assert service.browse([small["id"]], offset=10)["next_offset"] is None
    assert not service.browse([small["id"]], offset=10)["truncated"]


@pytest.mark.parametrize("options", [{"limit": 0}, {"limit": 51}, {"limit": True}, {"limit": "2"},
                                     {"offset": -1}, {"offset": 10001}, {"offset": False}, {"offset": 1.5}])
def test_invalid_paging(service, options):
    kb = base(service)
    with pytest.raises(KnowledgeError) as error:
        service.browse([kb["id"]], **options)
    assert error.value.code == "invalid_input"


def test_invalid_mounts_folders_and_deleted_scopes(service):
    kb, other = base(service), base(service, "Other")
    folder = service.create_folder(other["id"], "Other Folder")
    file_id = item(service, kb, "not_a_folder")
    for mounts, code in [([], "invalid_scope"), ([kb["id"]] * 2, "duplicate_scope"),
                         ([uuid4().hex for _ in range(21)], "invalid_scope"), ([uuid4().hex], "not_found"),
                         (None, "invalid_scope")]:
        with pytest.raises(KnowledgeError) as error:
            service.browse(mounts)
        assert error.value.code == code
    for folder_id in [folder["id"], file_id, uuid4().hex]:
        with pytest.raises(KnowledgeError) as error:
            service.browse([kb["id"]], folder_id=folder_id)
        assert error.value.code == "invalid_scope"
    service.delete_item(other["id"], folder["id"], folder["updated_at"])
    with pytest.raises(KnowledgeError) as error:
        service.browse([other["id"]], folder_id=folder["id"])
    assert error.value.code == "invalid_scope"
    service.delete(other["id"], service.get(other["id"])["updated_at"])
    with pytest.raises(KnowledgeError) as error:
        service.browse([other["id"]])
    assert error.value.code == "not_found"


@pytest.mark.parametrize("mode", ["keyword", "semantic", "hybrid"])
@pytest.mark.parametrize("query", ["*", "%", "???", "", " \n\t ", "___", "* % ?", "。！？", "😀", None, 42, "a" * 4001])
def test_invalid_queries_fail_before_any_provider(service, mode, query):
    kb = base(service)
    item(service, kb, "ready")
    with pytest.raises(KnowledgeError) as error:
        service.search([kb["id"]], query, mode=mode)
    assert error.value.code == "invalid_query" and str(error.value) == INVALID_QUERY_MESSAGE


@pytest.mark.parametrize("query", ["中文", "日本語", "한국어", "123", "apple*", "%apple", "C++", "  apple!?  "])
def test_meaningful_unicode_and_punctuation_keep_keyword_behavior(service, query):
    kb = base(service)
    file_id = item(service, kb, "ready")
    service.reranker_factory = lambda: None
    result = service.search([kb["id"]], query, mode="keyword")
    assert {row["document_id"] for row in result["results"]} == {file_id}
    assert validate_query(query) == query.strip()


def test_query_helper_length_and_import_are_independent_of_application_data(tmp_path):
    assert validate_query("a" * 4000) == "a" * 4000
    script = '''
import sqlite3, sys
sys.path.insert(0, sys.argv[1])
def forbidden(*args, **kwargs):
    raise AssertionError("Metadata must not be opened")
sqlite3.connect = forbidden
from knowledge_base.query import validate_query
assert validate_query(" 中文 ") == "中文"
assert "utilities.config" not in sys.modules
'''
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", script, str(Path(__file__).resolve().parents[1])],
                            cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert result.returncode == 0, result.stderr
