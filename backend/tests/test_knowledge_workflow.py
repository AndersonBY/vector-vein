"""Legacy workflow compatibility using real task wrappers and injected KB services."""
from pathlib import Path

import pytest

from worker.tasks import vector_db


@pytest.fixture
def adapter(monkeypatch):
    monkeypatch.setattr(vector_db.Workflow, "report_workflow_status", lambda *args: None)
    monkeypatch.setattr(vector_db.Workflow, "report_node_status", lambda *args: None)
    return vector_db


def workflow_data(values, action="add_data"):
    return {
        "nodes": [{
            "id": "node", "type": "Knowledge", "category": "vectorDb",
            "data": {"task_name": f"vector_db.{action}",
                     "template": {key: {"value": value} for key, value in values.items()}},
        }],
        "edges": [],
    }


def field_value(data, field):
    return data["nodes"][0]["data"]["template"][field]["value"]


class Service:
    def __init__(self):
        self.calls = []
        self.items = {}
        self.hits = [{"kb_id": "base", "document_id": "old-id", "text": "source A"},
                     {"kb_id": "base", "document_id": "other-id", "text": "source B"}]
        self.warnings = []

    def dispatch(self, action, payload):
        self.calls.append((action, payload))
        if action == "add_text":
            item = {"id": str(len(self.items)), "kb_id": payload["kb_id"], "kind": "file",
                    "status": "ready", "updated_at": "revision", **payload}
            self.items[item["id"]] = item
            return item
        if action == "get_item":
            return self.items[payload["id"]]
        if action == "delete_item":
            del self.items[payload["id"]]
            return True
        if action == "search":
            return {"results": self.hits, "warnings": self.warnings}
        pytest.fail(f"Unexpected service action: {action}")


@pytest.fixture
def service(adapter, monkeypatch):
    service = Service()
    monkeypatch.setattr(adapter, "knowledge_service", lambda: service)
    return service


def add_fields(**changes):
    return {"database": "base", "text": "body", "content_title": "title",
            "source_url": "https://example.org/source", **changes}


def test_saved_node_identities_remain_registered(adapter):
    source = (Path(__file__).parents[1] / "worker/tasks/vector_db.py").read_text(encoding="utf-8-sig")
    import ast
    functions = {node.name: node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)}
    for name in ("add_data", "delete_data", "search_data"):
        assert [decorator.id for decorator in functions[name].decorator_list] == ["task", "timer"]
        assert getattr(adapter, name).celery_task.name == f"tasks.vector_db.{name}"
    assert "UserVectorDatabase" not in source
    assert "background_task" not in source


@pytest.mark.parametrize("texts,expected", [("body", "0"), (["body"], ["0"]),
                                           (["one", "two"], ["0", "1"])])
def test_add_preserves_shape_expansion_and_source(adapter, service, texts, expected):
    data = workflow_data(add_fields(text=texts, wait_for_processing=True))
    assert adapter.add_data(data, "node") is data
    assert field_value(data, "object_id") == expected
    assert data["node_timeline"]["node"]["status"] == "SUCCEEDED"
    assert data["node_run_time"]["node"] >= 0
    stored = list(service.items.values())
    assert all(item["kb_id"] == "base" and item["source_url"] == "https://example.org/source"
               and item["name"] == "title" for item in stored)
    assert [item["text"] for item in stored] == ([texts] if isinstance(texts, str) else texts)


def test_add_expands_text_against_titles_and_rejects_mismatched_batch(adapter, service):
    data = workflow_data(add_fields(content_title=["first", "second"]))
    adapter.add_data(data, "node")
    assert [item["name"] for item in service.items.values()] == ["first", "second"]
    service.calls.clear()
    with pytest.raises(ValueError, match="equal lengths"):
        adapter.add_data(workflow_data(add_fields(text=["a", "b"], content_title=["a", "b", "c"])), "node")
    assert not service.calls


def test_add_without_wait_or_optional_source_returns_immediately(adapter, service):
    fields = add_fields()
    fields.pop("source_url")
    data = workflow_data(fields)
    adapter.add_data(data, "node")
    assert field_value(data, "object_id") == "0"
    assert service.items["0"]["source_url"] == ""
    assert [action for action, _ in service.calls] == ["add_text"]


@pytest.mark.parametrize("value", [None, 123, ["text", None]])
def test_invalid_batch_values_fail_before_service_mutation(adapter, service, value):
    with pytest.raises(ValueError, match="string"):
        adapter.add_data(workflow_data(add_fields(text=value)), "node")
    assert not service.calls


@pytest.mark.parametrize("status", ["failed", "unindexed", "unknown"])
def test_wait_reports_failed_and_unindexed_documents(adapter, service, status):
    service.items["old-id"] = {"id": "old-id", "kb_id": "base", "kind": "file", "status": status}
    with pytest.raises(RuntimeError, match="reindex|unsupported"):
        adapter._wait_for_processing(service, "base", ["old-id"])


def test_wait_is_bounded_and_checks_queued_then_ready(adapter, service, monkeypatch):
    item = {"id": "old-id", "kb_id": "base", "kind": "file", "status": "queued"}
    service.items["old-id"] = item
    ticks = iter([0, 0, 301])
    monkeypatch.setattr(adapter.time, "monotonic", lambda: next(ticks))
    sleeps = []
    monkeypatch.setattr(adapter.time, "sleep", sleeps.append)
    with pytest.raises(TimeoutError, match="Reindex"):
        adapter._wait_for_processing(service, "base", ["old-id"])
    assert sleeps == [1]
    monkeypatch.setattr(adapter.time, "monotonic", lambda: 0)
    monkeypatch.setattr(adapter.time, "sleep", lambda _: item.update(status="ready"))
    adapter._wait_for_processing(service, "base", ["old-id"])


@pytest.mark.parametrize("ids", ["old-id", ["old-id", "old-id"]])
def test_delete_uses_preserved_document_id_and_scoped_revision(adapter, service, ids):
    service.items["old-id"] = {"id": "old-id", "kb_id": "base", "kind": "file", "updated_at": "rev"}
    data = workflow_data({"database": "base", "object_id": ids}, "delete_data")
    adapter.delete_data(data, "node")
    assert field_value(data, "delete_success") is True
    assert service.calls[-1] == ("delete_item", {"kb_id": "base", "id": "old-id", "expected_updated_at": "rev"})
    assert len([call for call in service.calls if call[0] == "delete_item"]) == 1


def test_delete_preflights_entire_batch_and_rejects_other_base(adapter, service):
    service.items.update({"first": {"id": "first", "kb_id": "base", "kind": "file", "updated_at": "rev"},
                          "second": {"id": "second", "kb_id": "other", "kind": "file"}})
    with pytest.raises(ValueError, match="selected knowledge base"):
        adapter.delete_data(workflow_data({"database": "base", "object_id": ["first", "second"]}, "delete_data"), "node")
    assert all(action != "delete_item" for action, _ in service.calls)


@pytest.mark.parametrize("query,output_type,expected", [
    ("q", "text", "source A\nsource B"), ("q", "list", ["source A", "source B"]),
    (["q", "q2"], "text", ["source A\nsource B", "source A\nsource B"]),
    (["q"], "list", [["source A", "source B"]]), ([], "list", []),
])
def test_search_returns_source_text_and_legacy_output_shape(adapter, service, query, output_type, expected):
    data = workflow_data({"database": "base", "search_text": query, "output_type": output_type, "count": 2}, "search_data")
    adapter.search_data(data, "node")
    assert field_value(data, "output") == expected
    assert all(payload["kb_ids"] == ["base"] and payload["mode"] == "hybrid" and payload["limit"] == 2
               for _, payload in service.calls)


def test_search_rejects_out_of_scope_results(adapter, service):
    service.hits[0]["kb_id"] = "other"
    with pytest.raises(RuntimeError, match="outside"):
        adapter.search_data(workflow_data(
            {"database": "base", "search_text": "q", "output_type": "text", "count": 2}, "search_data"), "node")


@pytest.mark.parametrize("code", ["semantic_unavailable", "index_incomplete", "unindexed"])
@pytest.mark.parametrize("output_type", ["text", "list"])
def test_empty_search_with_retrieval_warning_fails_actionably(adapter, service, code, output_type):
    service.hits = []
    service.warnings = [{"kb_id": "base", "error_code": code, "message": "SYNTHETIC-SECRET"}]
    data = workflow_data({
        "database": "base", "search_text": "q", "output_type": output_type, "count": 2,
        "output": "previous output",
    }, "search_data")
    with pytest.raises(RuntimeError, match="Reindex") as caught:
        adapter.search_data(data, "node")
    assert "embedding model settings" in str(caught.value)
    assert "SYNTHETIC-SECRET" not in str(caught.value)
    assert field_value(data, "output") == "previous output"
    assert data["node_timeline"]["node"]["status"] == "FAILED"
    assert data["failures"][0]["task_name"] == "vector_db.search_data"
    assert data["failures"][0]["message"] == str(caught.value)


@pytest.mark.parametrize("code", ["semantic_unavailable", "index_incomplete", "unindexed"])
@pytest.mark.parametrize("output_type,expected", [
    ("text", "source A\nsource B"), ("list", ["source A", "source B"]),
])
def test_warning_keeps_useful_lexical_fallback(adapter, service, code, output_type, expected):
    service.warnings = [{"kb_id": "base", "error_code": code}]
    data = workflow_data({
        "database": "base", "search_text": "q", "output_type": output_type, "count": 2,
    }, "search_data")
    adapter.search_data(data, "node")
    assert field_value(data, "output") == expected
    assert data["node_timeline"]["node"]["status"] == "SUCCEEDED"
    assert not data.get("failures")


@pytest.mark.parametrize("warnings", [[], [{"error_code": "informational"}]])
@pytest.mark.parametrize("output_type,expected", [("text", ""), ("list", [])])
def test_empty_search_without_retrieval_problem_is_success(adapter, service, warnings, output_type, expected):
    service.hits = []
    service.warnings = warnings
    data = workflow_data({
        "database": "base", "search_text": "q", "output_type": output_type, "count": 2,
    }, "search_data")
    adapter.search_data(data, "node")
    assert field_value(data, "output") == expected
    assert data["node_timeline"]["node"]["status"] == "SUCCEEDED"


def test_batch_search_does_not_publish_partial_output_when_one_query_is_unavailable(adapter, service, monkeypatch):
    dispatch = service.dispatch

    def search(action, payload):
        response = dispatch(action, payload)
        if payload["query"] == "unavailable":
            return {"results": [], "warnings": [{"error_code": "semantic_unavailable"}]}
        return response

    monkeypatch.setattr(service, "dispatch", search)
    data = workflow_data({
        "database": "base", "search_text": ["q", "unavailable"], "output_type": "list", "count": 2,
        "output": "previous output",
    }, "search_data")
    with pytest.raises(RuntimeError, match="retry"):
        adapter.search_data(data, "node")
    assert field_value(data, "output") == "previous output"
    assert data["node_timeline"]["node"]["status"] == "FAILED"
    assert [payload["query"] for _, payload in service.calls] == ["q", "unavailable"]


def test_real_service_batch_source_search_and_scoped_delete(adapter, monkeypatch, tmp_path):
    from knowledge_base import KnowledgeError, KnowledgeService

    class Vectors:
        def write(self, *args):
            pass

        def search(self, *args):
            return []

        def delete_document(self, *args, **kwargs):
            pass

        def close(self):
            pass

    class Embedder:
        def get(self, text):
            return [[1.0, 0.0] for _ in text] if isinstance(text, list) else [1.0, 0.0]

    service = KnowledgeService(tmp_path / "knowledge", vector_store=Vectors(),
                               embedder_factory=lambda _: Embedder(), start_worker=False)
    monkeypatch.setattr(adapter, "knowledge_service", lambda: service)
    try:
        base = service.create(name="Workflow", embedding_provider="test", embedding_model="test")
        other = service.create(name="Other", embedding_provider="test", embedding_model="test")
        data = workflow_data(add_fields(database=base["id"], text=["needle first", "needle second"]))
        adapter.add_data(data, "node")
        ids = field_value(data, "object_id")
        assert len(set(ids)) == 2
        items = [service.dispatch("get_item", {"kb_id": base["id"], "id": key}) for key in ids]
        assert len({item["name"] for item in items}) == 2
        assert all(item["source_url"] == "https://example.org/source" and item["status"] == "queued"
                   for item in items)
        service.run_pending()
        adapter._wait_for_processing(service, base["id"], ids)
        search = workflow_data(
            {"database": base["id"], "search_text": "needle", "output_type": "list", "count": 5}, "search_data")
        adapter.search_data(search, "node")
        assert set(field_value(search, "output")) == {"needle first", "needle second"}
        with pytest.raises(KnowledgeError, match="no longer exists"):
            adapter.delete_data(workflow_data({"database": other["id"], "object_id": ids}, "delete_data"), "node")
        assert service.get_item(base["id"], ids[0])["status"] == "ready"
        adapter.delete_data(workflow_data({"database": base["id"], "object_id": ids}, "delete_data"), "node")
        assert service.items(base["id"])["total"] == 0
    finally:
        service.close()
