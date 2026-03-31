from __future__ import annotations

from types import SimpleNamespace

import pytest

from background_task import qdrant_tasks


def test_get_qdrant_client_reuses_shared_instance(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    created: list[dict[str, object]] = []

    class _FakeClient:
        def __init__(self, **kwargs: object) -> None:
            created.append(kwargs)

        def close(self) -> None:
            created.append({"closed": True})

    monkeypatch.setattr(qdrant_tasks, "_QDRANT_CLIENT", None)
    monkeypatch.setattr(qdrant_tasks, "QdrantClient", _FakeClient)
    monkeypatch.setattr(qdrant_tasks, "config", SimpleNamespace(data_path=str(tmp_path)))

    first = qdrant_tasks.get_qdrant_client()
    second = qdrant_tasks.get_qdrant_client()

    assert first is second
    assert created == [
        {
            "path": tmp_path.joinpath("qdrant_db").as_posix(),
            "force_disable_check_same_thread": True,
        }
    ]

    qdrant_tasks.close_qdrant_client()
    assert qdrant_tasks._QDRANT_CLIENT is None
    assert created[-1] == {"closed": True}


def test_search_points_sync_uses_query_points_and_returns_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, object] = {}

    class _FakeClient:
        def query_points(self, **kwargs: object) -> SimpleNamespace:
            recorded.update(kwargs)
            return SimpleNamespace(
                points=[
                    SimpleNamespace(payload={"text": "first"}),
                    SimpleNamespace(payload={"text": "second"}),
                ]
            )

    monkeypatch.setattr(qdrant_tasks, "get_qdrant_client", lambda: _FakeClient())

    results = qdrant_tasks.search_points_sync("db-1", [0.1, 0.2], limit=7)

    assert results == [{"text": "first"}, {"text": "second"}]
    assert recorded == {
        "collection_name": "db-1_text_collection",
        "query": [0.1, 0.2],
        "limit": 7,
        "with_payload": True,
        "with_vectors": False,
    }
