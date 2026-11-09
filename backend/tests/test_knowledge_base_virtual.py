from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from knowledge_base import KnowledgeError, KnowledgeService
from knowledge_base.virtual import mount_aliases, virtual_operation


class NoVectors:
    def close(self):
        pass


@pytest.fixture
def source(tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("VFS must not call providers")
    service = KnowledgeService(tmp_path / "kb", embedder_factory=forbidden, reranker_factory=forbidden,
                               vector_store=NoVectors(), start_worker=False)
    first = service.create("Guides", "test", "test")
    second = service.create("Other", "test", "test")
    mounts = [{"kb_id": kb["id"], "name": kb["name"]} for kb in (first, second)]
    yield SimpleNamespace(service=service, first=first, second=second, mounts=mounts)
    service.close()


def document(source, name="Manual.pdf", *, kb=None, parent=None, text="Extracted 中文正文.\nSecond line.", status="ready"):
    service = source.service
    with service._write():
        key = service._insert_item((kb or source.first)["id"], parent, name, "file", text=text,
                                   original="PRIVATE_RAW_DOCUMENT_PATH", source_url="https://private.invalid")
        service._db.execute("UPDATE items SET status=?,generation=1,active_token=? WHERE id=?", (status, uuid4().hex, key))
    return key


def invoke(source, action, path=".knowledge", **args):
    return virtual_operation(source.service, source.mounts, {"action": action, "path": path, **args})


def test_aliases_are_pure_safe_stable_and_collision_free(tmp_path):
    mounts = [{"kb_id": f"{index:032x}", "name": name} for index, name in enumerate(
        ["Docs", "docs", "../../", "A/B", "A\\B", "中文 知识库", "C:/secret%2f.."]) ]
    original = deepcopy(mounts)
    aliases = mount_aliases(mounts)
    assert aliases == mount_aliases(list(reversed(mounts)))
    assert len(aliases) == len(set(alias.casefold() for alias in aliases)) == len(mounts)
    assert mounts == original
    assert all(not any(token in alias for token in ["/", "\\", ":", "%", ".."]) for alias in aliases)
    assert f"Docs--{mounts[0]['kb_id']}" in aliases
    # Adversarial frozen names cannot collide with generated aliases.
    collision = mounts + [{"kb_id": "f" * 32, "name": f"Docs--{mounts[0]['kb_id']}"}]
    assert len(mount_aliases(collision)) == len(collision)
    script = '''
import sys, sqlite3
sys.path.insert(0, sys.argv[1])
def deny(*args, **kwargs):
    raise AssertionError("No store/index should open")
sqlite3.connect = deny
from knowledge_base.virtual import mount_aliases
assert mount_aliases([{"kb_id": "a"*32, "name": "Docs"}]) == {"Docs": "a"*32}
assert "utilities.config" not in sys.modules and "qdrant_client" not in sys.modules
'''
    result = subprocess.run([sys.executable, "-c", script, str(Path(__file__).resolve().parents[1])], cwd=tmp_path,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("path", ["/etc/passwd", "C:/private", ".knowledge/../outside", ".knowledge/./Guides",
    ".knowledge/Guides/../../outside", ".knowledge\\Guides", ".knowledge/%2e%2e", ".knowledge/%252e%252e",
    ".knowledge/Guides%2fManual.pdf", ".knowledge//Guides", ".knowledgeevil/Guides", ".knowledge/Guides\x00", ""])
def test_escaping_paths_are_rejected(source, path):
    with pytest.raises(KnowledgeError) as error:
        invoke(source, "read", path)
    assert error.value.code == "invalid_path"
    assert "private" not in str(error.value)


def test_root_nested_recursive_and_multikb_lists(source):
    folder = source.service.create_folder(source.first["id"], "Folder")
    document(source)
    child = document(source, "Nested.docx", parent=folder["id"])
    document(source, "Other.txt", kb=source.second)
    root = invoke(source, "list", recursive=False)
    assert [entry["path"] for entry in root["entries"]] == [".knowledge/Guides", ".knowledge/Other"]
    assert root["total"] == 2 and root["next_offset"] is None
    assert all(entry["kind"] == "folder" and entry["size"] == 0 for entry in root["entries"])
    recursive = invoke(source, "list")
    assert recursive["total"] == 6
    assert {entry["path"] for entry in recursive["entries"]} == {
        ".knowledge/Guides", ".knowledge/Other", ".knowledge/Guides/Folder", ".knowledge/Guides/Manual.pdf",
        ".knowledge/Guides/Folder/Nested.docx", ".knowledge/Other/Other.txt"}
    assert invoke(source, "list", ".knowledge/Guides", recursive=False)["total"] == 2
    assert invoke(source, "list", ".knowledge/Guides")["total"] == 3
    nested = invoke(source, "list", ".knowledge/Guides/Folder")["entries"]
    assert len(nested) == 1 and nested[0]["document_id"] == child
    root_stat = invoke(source, "stat", ".knowledge/")
    assert root_stat["path"] == ".knowledge" and root_stat["kb_id"] is None and root_stat["size"] == 0


def test_scope_is_applied_before_traversal_even_for_cross_kb_parent(source):
    folder = source.service.create_folder(source.first["id"], "Folder")
    document(source, "PRIVATE_NAME", kb=source.second, parent=folder["id"])
    mounted = [source.mounts[0]]
    result = virtual_operation(source.service, mounted, {"action": "list", "path": ".knowledge"})
    assert result["total"] == 2 and "PRIVATE" not in json.dumps(result)
    for path in [".knowledge/Other", ".knowledge/Guides/Folder/PRIVATE_NAME"]:
        with pytest.raises(KnowledgeError) as error:
            virtual_operation(source.service, mounted, {"action": "stat", "path": path})
        assert error.value.code == "not_found"


def test_list_is_metadata_only_and_all_vfs_operations_are_readonly(source):
    document(source)
    reads = []
    def authorize(action, table, column, *args):
        if action == sqlite3.SQLITE_READ:
            reads.append((table, column))
            if table == "items" and column in {"original", "source_url", "extracted_text"}:
                return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    before = source.service._db.total_changes
    source.service._db.set_authorizer(authorize)
    try:
        result = invoke(source, "list")
    finally:
        source.service._db.set_authorizer(None)
    stat = invoke(source, "stat", ".knowledge/Guides/Manual.pdf")
    read = invoke(source, "read", stat["path"], expected_version=stat["version"])
    assert reads and source.service._db.total_changes == before
    assert "PRIVATE" not in json.dumps([result, stat, read])
    assert str(source.service.root) not in json.dumps([result, stat, read])
    for action in ["write", "delete", "move", "mkdir"]:
        with pytest.raises(KnowledgeError) as error:
            invoke(source, action)
        assert error.value.code == "read_only"


def test_pdf_and_office_use_extracted_text_and_character_pages(source):
    content = "中文😀内容\n" * 40
    document(source, text=content)
    document(source, "Document.docx", text="Office extracted text")
    path = ".knowledge/Guides/Manual.pdf"
    stat = invoke(source, "stat", path)
    assert stat["size"] == len(content.encode("utf-8"))
    listed = next(entry for entry in invoke(source, "list")["entries"] if entry["path"] == path)
    assert listed["version"] == stat["version"] and "size" not in listed
    trace = []
    source.service._db.set_trace_callback(trace.append)
    try:
        first = invoke(source, "read", path, limit=7, expected_version=stat["version"])
        second = invoke(source, "read", path, offset=first["next_offset"], limit=7, expected_version=first["version"])
    finally:
        source.service._db.set_trace_callback(None)
    assert first["text"] + second["text"] == content[:14]
    assert first["total"] == len(content) and first["offset"] == 0 and second["offset"] == 7
    assert any("substr(extracted_text" in sql for sql in trace)
    assert invoke(source, "read", ".knowledge/Guides/Document.docx")["text"] == "Office extracted text"
    assert invoke(source, "read", path, offset=len(content))["next_offset"] is None


@pytest.mark.parametrize("status,code", [("queued", "indexing"), ("indexing", "indexing"),
                                        ("failed", "source_unavailable"), ("ready", "source_unavailable"),
                                        ("unindexed", "source_unavailable")])
def test_empty_text_has_explicit_error(source, status, code):
    document(source, status=status, text="")
    with pytest.raises(KnowledgeError) as error:
        invoke(source, "read", ".knowledge/Guides/Manual.pdf")
    assert error.value.code == code


def test_failed_embedding_does_not_hide_available_extracted_text(source):
    document(source, status="failed", text="Available extracted source")
    assert invoke(source, "read", ".knowledge/Guides/Manual.pdf")["text"] == "Available extracted source"


def test_rename_move_delete_and_reindex_invalidate_paths_or_versions(source):
    service, kb = source.service, source.first["id"]
    key = document(source)
    path = ".knowledge/Guides/Manual.pdf"
    version = invoke(source, "stat", path)["version"]
    service.update(kb, "Renamed KB", service.get(kb)["updated_at"])
    assert mount_aliases(source.mounts)["Guides"] == kb
    assert invoke(source, "stat", path)["version"] == version
    item = service.get_item(kb, key)
    renamed = service.rename(kb, key, "Renamed.pdf", item["updated_at"])
    with pytest.raises(KnowledgeError):
        invoke(source, "stat", path)
    path = ".knowledge/Guides/Renamed.pdf"
    with pytest.raises(KnowledgeError) as error:
        invoke(source, "read", path, expected_version=version)
    assert error.value.code == "stale_source"
    folder = service.create_folder(kb, "Folder")
    service.move(kb, key, renamed["updated_at"], folder["id"])
    with pytest.raises(KnowledgeError):
        invoke(source, "read", path)
    path = ".knowledge/Guides/Folder/Renamed.pdf"
    first = invoke(source, "read", path, limit=3)
    service.reindex(kb, key)
    with pytest.raises(KnowledgeError) as error:
        invoke(source, "read", path, offset=3, expected_version=first["version"])
    assert error.value.code == "stale_source"
    service.delete_item(kb, key, service.get_item(kb, key)["updated_at"])
    with pytest.raises(KnowledgeError) as error:
        invoke(source, "read", path)
    assert error.value.code == "not_found"


def test_page_bounds_and_offset_ceiling(source):
    db = source.service._db
    with source.service._write():
        db.executemany("INSERT INTO items(id,kb_id,kind,name,status,created_at,updated_at) VALUES(?,?,'file',?,'queued','t','t')",
                       [(uuid4().hex, source.first["id"], f"file{index:05}.pdf") for index in range(10003)])
    first = invoke(source, "list", ".knowledge/Guides", limit=2)
    second = invoke(source, "list", ".knowledge/Guides", offset=first["next_offset"], limit=2)
    assert first["total"] == 10003 and first["truncated"] and first["next_offset"] == 2
    assert set(entry["path"] for entry in first["entries"]).isdisjoint(entry["path"] for entry in second["entries"])
    capped = invoke(source, "list", ".knowledge/Guides", offset=10000, limit=1)
    assert capped["next_offset"] is None and capped["truncated"]
    for args in [{"action": "list", "limit": 5001}, {"action": "list", "offset": 10001},
                 {"action": "list", "recursive": 1}, {"action": "list", "offset": True},
                 {"action": "read", "limit": 262145}, {"action": "read", "offset": -1},
                 {"action": "read", "expected_version": None}]:
        with pytest.raises(KnowledgeError) as error:
            virtual_operation(source.service, source.mounts, {"path": ".knowledge", **args})
        assert error.value.code == "invalid_input"


@pytest.fixture
def bridge(source, tmp_path, monkeypatch):
    import knowledge_base
    from task_agent import knowledge, service
    from task_agent.store import BusinessStore, now
    root = tmp_path / "tasks"
    store = BusinessStore(root / "tasks.db")
    snapshot = {"knowledge_bases": source.mounts, "agent_profile": {"knowledge_base_ids": [item["kb_id"] for item in source.mounts]}}
    store.create_task({"tid": "task", "thread_id": "task", "title": "Test", "goal": "Test", "status": "PENDING",
                       "current_turn_id": "task/turn/1", "model_provider": "local", "model": "synthetic",
                       "reasoning_effort": "default", "config_snapshot": snapshot, "created_at": now(), "updated_at": now()})
    monkeypatch.setattr(knowledge_base, "knowledge_service", lambda: source.service)
    monkeypatch.setattr(service, "task_agent_service", lambda: SimpleNamespace(task_root=root))
    knowledge.start_knowledge_bridge("http://127.0.0.1:9876")
    app = FastAPI()
    knowledge.install_knowledge_routes(app)
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 1234)) as client:
        def request(arguments, **changes):
            return client.post(knowledge._PATH + "/vfs", json={"task_id": "task", "mounts": source.mounts,
                                                              "arguments": arguments, **changes},
                               headers={"Authorization": "Bearer " + knowledge._token})
        yield store, request
    knowledge.stop_knowledge_bridge()


def test_bridge_vfs_rechecks_saved_authority_and_sanitizes_errors(source, bridge):
    store, request = bridge
    key = document(source)
    args = {"action": "stat", "path": ".knowledge/Guides/Manual.pdf"}
    response = request(args)
    assert response.status_code == 200 and response.json()["document_id"] == key
    invalid = request({"action": "read", "path": "C:/private/SECRET"})
    assert invalid.status_code == 400 and invalid.json()["error_code"] == "invalid_path"
    assert "SECRET" not in invalid.text
    stale = request({**args, "action": "read", "expected_version": "old"})
    assert stale.status_code == 400 and stale.json()["error_code"] == "stale_source"
    assert request({"action": "list", "path": ".knowledge", "kb_ids": [source.first["id"]]}).status_code == 400
    assert request(args, task_id="missing").status_code == 400
    assert request(args, mounts=[source.mounts[1]]).status_code == 400
    with store.connect() as db:
        db.execute("UPDATE tasks SET config_snapshot=? WHERE tid='task'", (json.dumps({"knowledge_bases": [],
                   "agent_profile": {"knowledge_base_ids": []}}),))
    assert request(args).status_code == 400


def test_bridge_deleted_mount_never_becomes_global_list(source, bridge):
    _, request = bridge
    source.service.delete(source.first["id"], source.service.get(source.first["id"])["updated_at"])
    result = request({"action": "list", "path": ".knowledge"})
    assert result.status_code == 400 and result.json()["error_code"] == "not_found"


def test_bridge_legacy_results_add_virtual_paths_without_mutating_service_responses(source, bridge, monkeypatch):
    from task_agent import knowledge
    store, _ = bridge
    root = store.path.parent
    service = source.service
    key = document(source)
    legacy_hit = {"kb_id": source.first["id"], "document_id": key, "path": "Manual.pdf", "text": "evidence"}
    search_result = {"results": [legacy_hit], "warnings": []}
    monkeypatch.setattr(service, "dispatch", lambda *args: search_result)
    def dispatch(operation, arguments):
        return knowledge._dispatch(root, operation, {"task_id": "task", "mounts": source.mounts, "arguments": arguments})
    hit = dispatch("search", {"query": "evidence"})["results"][0]
    assert hit["path"] == "Manual.pdf" and hit["knowledge_path"] == ".knowledge/Guides/Manual.pdf"
    assert "knowledge_path" not in legacy_hit
    read = dispatch("read", {"document_id": key})
    assert read["path"] == "Manual.pdf" and read["knowledge_path"] == hit["knowledge_path"]
    assert "knowledge_path" not in service.read_document([source.first["id"]], key)
    browse = dispatch("browse", {})
    assert next(entry for entry in browse["items"] if entry["id"] == key)["knowledge_path"] == hit["knowledge_path"]
    assert {base["mount_path"] for base in browse["bases"]} == {".knowledge/Guides", ".knowledge/Other"}
    assert "knowledge_path" not in service.browse([source.first["id"]])["items"][0]
    assert invoke(source, "read", hit["knowledge_path"])["text"] == read["text"]


def test_empty_mounts_list_empty_without_becoming_global_query(source):
    assert mount_aliases([]) == {}
    assert virtual_operation(source.service, [], {"action": "list"}) == {
        "entries": [], "total": 0, "next_offset": None, "truncated": False}


def test_read_maximum_page_is_bounded_and_replacement_at_same_path_is_stale(source):
    content = "字" * 262145
    key = document(source, text=content)
    path = ".knowledge/Guides/Manual.pdf"
    first = invoke(source, "read", path, limit=262144)
    assert len(first["text"]) == 262144 and first["next_offset"] == 262144
    last = invoke(source, "read", path, offset=first["next_offset"], limit=262144, expected_version=first["version"])
    assert last["text"] == "字" and last["next_offset"] is None
    source.service.delete_item(source.first["id"], key, source.service.get_item(source.first["id"], key)["updated_at"])
    document(source, text="Different source at the same name")
    with pytest.raises(KnowledgeError) as error:
        invoke(source, "read", path, offset=first["next_offset"], expected_version=first["version"])
    assert error.value.code == "stale_source"
