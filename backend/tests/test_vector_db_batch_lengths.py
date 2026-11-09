from __future__ import annotations

import pytest

from worker.tasks import vector_db


def workflow_data(**values):
    return {
        "nodes": [
            {
                "id": "add-data",
                "type": "AddData",
                "category": "vectorDb",
                "data": {
                    "task_name": "vector_db.add_data",
                    "template": {key: {"value": value} for key, value in values.items()},
                },
            }
        ],
        "edges": [],
    }


def install_mocks(monkeypatch):
    monkeypatch.setattr(vector_db.Workflow, "set_node_status", lambda *args: None)
    monkeypatch.setattr(vector_db.Workflow, "report_workflow_status", lambda *args: None)
    monkeypatch.setattr(vector_db.Workflow, "report_node_status", lambda *args: None)
    created = []
    service_lookups = []

    class Service:
        def dispatch(self, action, payload):
            assert action == "add_text"
            created.append(payload.copy())
            return {"id": f"synthetic-object-{len(created)}"}

    def get_service():
        service_lookups.append(True)
        return Service()

    monkeypatch.setattr(vector_db, "knowledge_service", get_service)
    monkeypatch.setattr(vector_db, "remove_markdown_image", lambda value: value)
    return created, service_lookups


def test_add_data_repeats_single_title_and_url_for_batch(monkeypatch):
    created, service_lookups = install_mocks(monkeypatch)
    data = workflow_data(
        text=["synthetic first", "synthetic second"],
        content_title="shared title",
        source_url="synthetic://source",
        database="synthetic-db",
        data_type="text",
        split_method="general",
        chunk_length=500,
    )

    result = vector_db.add_data(data, "add-data")

    assert [item["name"] for item in created] == ["shared title", "shared title"]
    assert [item["text"] for item in created] == ["synthetic first", "synthetic second"]
    assert [item["source_url"] for item in created] == ["synthetic://source"] * 2
    assert [item["kb_id"] for item in created] == ["synthetic-db"] * 2
    assert service_lookups == [True]
    assert result["nodes"][0]["data"]["template"]["object_id"]["value"] == [
        "synthetic-object-1",
        "synthetic-object-2",
    ]


def test_add_data_rejects_incompatible_batch_lengths_before_writing(monkeypatch):
    created, service_lookups = install_mocks(monkeypatch)
    data = workflow_data(
        text=["synthetic first", "synthetic second"],
        content_title=["title one", "title two", "title that must not be dropped"],
        source_url="synthetic://source",
        database="synthetic-db",
        data_type="text",
        split_method="general",
        chunk_length=500,
    )

    with pytest.raises(ValueError, match="equal lengths"):
        vector_db.add_data(data, "add-data")

    assert service_lookups == []
    assert created == []
