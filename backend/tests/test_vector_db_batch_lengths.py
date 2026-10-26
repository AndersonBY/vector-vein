from __future__ import annotations

from types import SimpleNamespace

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
    uploaded = []
    database_lookups = []
    database = SimpleNamespace(
        vid=SimpleNamespace(hex="synthetic-db"),
        embedding_provider="mock",
        embedding_model="mock",
        embedding_size=2,
    )

    def create_object(**kwargs):
        created.append(kwargs)
        return SimpleNamespace(
            oid=SimpleNamespace(hex=f"synthetic-object-{len(created)}"),
            data_type=kwargs["data_type"],
            info={},
            raw_data=kwargs["raw_data"],
            save=lambda: None,
        )

    def get_database(**kwargs):
        database_lookups.append(kwargs)
        return database

    monkeypatch.setattr(vector_db, "UserObject", SimpleNamespace(create=create_object))
    monkeypatch.setattr(vector_db, "UserVectorDatabase", SimpleNamespace(get=get_database))
    monkeypatch.setattr(
        vector_db,
        "embedding_and_upload",
        SimpleNamespace(delay=lambda **kwargs: uploaded.append(kwargs)),
    )
    monkeypatch.setattr(vector_db, "remove_markdown_image", lambda value: value)
    monkeypatch.setattr(
        vector_db,
        "split_text",
        lambda text, rules, flat: [{"text": text, "word_counts": 1}],
    )
    return created, uploaded, database_lookups


def test_add_data_repeats_single_title_and_url_for_batch(monkeypatch):
    created, uploaded, database_lookups = install_mocks(monkeypatch)
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

    assert [item["title"] for item in created] == ["shared title", "shared title"]
    assert [item["source_url"] for item in created] == ["synthetic://source"] * 2
    assert len(uploaded) == 2
    assert len(database_lookups) == 1
    assert result["nodes"][0]["data"]["template"]["object_id"]["value"] == [
        "synthetic-object-1",
        "synthetic-object-2",
    ]


def test_add_data_rejects_incompatible_batch_lengths_before_writing(monkeypatch):
    created, uploaded, database_lookups = install_mocks(monkeypatch)
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

    assert database_lookups == []
    assert created == []
    assert uploaded == []
