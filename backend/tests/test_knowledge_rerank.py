from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import threading

import pytest

from knowledge_base import KnowledgeService
from test_knowledge_base import Embedder, base, text


def response(items):
    return SimpleNamespace(results=[SimpleNamespace(index=index, relevance_score=score, document="forged")
                                    for index, score in items])


@pytest.fixture
def service(tmp_path):
    instance = KnowledgeService(tmp_path / "kb", embedder_factory=lambda _: Embedder(),
                                reranker_factory=lambda: None, start_worker=False)
    yield instance
    instance.close()


@pytest.mark.parametrize("mode", ["keyword", "semantic", "hybrid"])
def test_rerank_expands_candidates_and_uses_only_original_content(service, mode):
    kb, other = base(service), base(service, "Other")
    for index in range(9):
        text(service, kb, name=str(index), value=f"apple {index}")
    text(service, other, value="private apple")
    service.run_pending()
    calls = []

    def rank(**kwargs):
        calls.append(kwargs)
        return response([(len(kwargs["documents"]) - 1, .9), (0, .5)])

    original = service.search([kb["id"]], "apple", mode=mode, limit=2)["results"]
    service.reranker_factory = lambda: SimpleNamespace(rerank=rank)
    result = service.search([kb["id"]], "apple", mode=mode, limit=2)
    assert len(calls[0]["documents"]) == 8
    assert "private apple" not in calls[0]["documents"]
    assert calls[0]["return_documents"] is False
    assert result["results"][0]["text"] == calls[0]["documents"][-1]
    assert result["results"][0]["score"] == .9
    assert result["results"][1]["chunk_id"] == original[0]["chunk_id"]
    assert not result["warnings"]


@pytest.mark.parametrize("items", [
    [(-1, .9)], [(8, .9)], [(0, .9), (0, .8)], [(True, .9)],
    [(0.5, .9)], [("0", .9)], [(0, float("inf"))], [(0, float("nan"))],
    [(0, "0.9")], [(0, True)], [],
])
def test_invalid_provider_results_preserve_original_order_with_safe_warning(service, items):
    kb = base(service)
    for index in range(8):
        text(service, kb, name=str(index), value=f"apple {index}")
    service.run_pending()
    original = service.search([kb["id"]], "apple", mode="keyword", limit=2)["results"]
    service.reranker_factory = lambda: SimpleNamespace(rerank=lambda **kwargs: response(items))
    result = service.search([kb["id"]], "apple", mode="keyword", limit=2)
    assert result["results"] == original
    assert result["warnings"][-1]["error_code"] == "rerank_unavailable"


def test_failure_and_factory_failure_do_not_disclose_exception(service):
    kb = base(service)
    text(service, kb)
    service.run_pending()
    original = service.search([kb["id"]], "apple", mode="keyword")["results"]

    def fail(**kwargs):
        raise RuntimeError("secret-key private-document https://user:password@example.invalid")

    for factory in (fail, lambda: SimpleNamespace(rerank=fail)):
        service.reranker_factory = factory
        result = service.search([kb["id"]], "apple", mode="keyword")
        assert result["results"] == original
        assert "secret-key" not in str(result)
        assert "password" not in str(result)
        assert result["warnings"][-1]["error_code"] == "rerank_unavailable"


def test_empty_candidates_do_not_construct_reranker(service):
    kb = base(service)
    service.reranker_factory = lambda: pytest.fail("No provider should be constructed")
    assert service.search([kb["id"]], "apple", mode="keyword") == {"results": [], "warnings": []}


def test_partial_response_preserves_unreturned_candidates(service):
    kb = base(service)
    for index in range(4):
        text(service, kb, name=str(index), value=f"apple {index}")
    service.run_pending()
    original = service.search([kb["id"]], "apple", mode="keyword", limit=4)["results"]
    service.reranker_factory = lambda: SimpleNamespace(rerank=lambda **kwargs: response([(3, .9)]))
    result = service.search([kb["id"]], "apple", mode="keyword", limit=4)
    assert [hit["chunk_id"] for hit in result["results"]] == [
        original[index]["chunk_id"] for index in [3, 0, 1, 2]]


@pytest.mark.parametrize("limit", [1, 50])
def test_candidate_bounds(service, limit):
    kb = base(service)
    for index in range(205):
        text(service, kb, name=str(index), value=f"apple {index}")
    service.run_pending()
    counts = []

    def rank(**kwargs):
        counts.append(len(kwargs["documents"]))
        return response([(index, 1.) for index in reversed(range(len(kwargs["documents"])))])

    service.reranker_factory = lambda: SimpleNamespace(rerank=rank)
    result = service.search([kb["id"]], "apple", mode="keyword", limit=limit)
    assert counts == [min(limit * 4, 200)]
    assert len(result["results"]) == limit


@pytest.mark.parametrize("mutation", ["delete", "reindex", "reindex_publish", "move", "delete_folder", "delete_base"])
@pytest.mark.parametrize("fails", [False, True])
def test_provider_does_not_hold_lock_and_final_scope_is_revalidated(service, mutation, fails):
    kb = base(service)
    folder = service.create_folder(kb["id"], "Scope")
    item = service.add_text(kb["id"], name="Note", text="apple secret", parent_id=folder["id"])
    service.run_pending()
    entered, release = threading.Event(), threading.Event()

    def rank(**kwargs):
        entered.set()
        assert release.wait(5)
        if fails:
            raise RuntimeError("secret")
        return response([(0, .9)])

    service.reranker_factory = lambda: SimpleNamespace(rerank=rank)
    with ThreadPoolExecutor(max_workers=2) as pool:
        searching = pool.submit(service.search, [kb["id"]], "apple", "keyword", folder["id"])
        try:
            assert entered.wait(5)

            def mutate():
                if mutation == "delete":
                    service.delete_item(kb["id"], item["id"], service.get_item(kb["id"], item["id"])["updated_at"])
                elif mutation in {"reindex", "reindex_publish"}:
                    service.reindex(kb["id"], item["id"])
                    if mutation == "reindex_publish":
                        service.run_pending()
                elif mutation == "move":
                    service.move(kb["id"], item["id"], service.get_item(kb["id"], item["id"])["updated_at"])
                elif mutation == "delete_folder":
                    service.delete_item(kb["id"], folder["id"], service.get_item(kb["id"], folder["id"])["updated_at"])
                else:
                    service.delete(kb["id"], service.get(kb["id"])["updated_at"])

            pool.submit(mutate).result(timeout=3)
        finally:
            release.set()
        result = searching.result(timeout=5)
    assert result["results"] == []
    assert bool(result["warnings"]) == fails
