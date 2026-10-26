from copy import deepcopy
from threading import Event, Thread

import diskcache
import pytest
from celery.exceptions import Retry

from utilities import workflow_timeline as timeline
from utilities.workflow import Workflow
from worker.tasks import task
from test_workflow_failures import workflow_data


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    with diskcache.Cache(str(tmp_path / "progress")) as cache:
        monkeypatch.setattr(timeline, "cache", cache)
        monkeypatch.setattr(Workflow, "report_node_status", lambda *args: True)
        monkeypatch.setattr(Workflow, "report_workflow_status", lambda *args: True)
        yield cache


def test_running_is_visible_while_task_blocks_and_siblings_survive():
    data = workflow_data("first", "second")
    timeline.reset_run(data)
    timeline.initialize_timeline(data)
    entered, release = Event(), Event()

    @task
    def blocked(data, node_id):
        entered.set()
        assert release.wait(5)
        return data

    first = deepcopy(data)
    thread = Thread(target=blocked, args=(first, "first"))
    thread.start()
    try:
        assert entered.wait(5)
        assert timeline.read_timeline(data)["first"]["status"] == "RUNNING"
        second = deepcopy(data)
        timeline.update_timeline(second, "second", "RUNNING")
        timeline.update_timeline(second, "second", "SUCCEEDED")
    finally:
        release.set()
        thread.join(5)
    result = timeline.read_timeline(data)
    assert {entry["status"] for entry in result.values()} == {"SUCCEEDED"}
    assert result["first"]["finished_at"] >= result["first"]["started_at"]


def test_retry_waiting_preserves_first_start_and_then_succeeds(monkeypatch):
    data = workflow_data("node")
    attempts = []

    @task
    def retried(data, node_id):
        if not attempts:
            attempts.append(True)
            retried.retry(data, node_id)
        return data

    def retry(**kwargs):
        return Retry("later")

    monkeypatch.setattr(retried.celery_task, "retry", retry)
    with pytest.raises(Retry):
        retried(data, "node")
    waiting = timeline.read_timeline(data)["node"]
    assert waiting["status"] == "WAITING" and not data.get("failures")
    result = retried(data, "node")
    assert result["node_timeline"]["node"]["status"] == "SUCCEEDED"
    assert result["node_timeline"]["node"]["started_at"] == waiting["started_at"]


def test_failed_cause_survives_progress_cache_failure(monkeypatch):
    data = workflow_data("node")
    monkeypatch.setattr(timeline, "cache", None)

    @task
    def failed(data, node_id):
        raise ValueError("actual cause")

    with pytest.raises(ValueError, match="actual cause"):
        failed(data, "node")
    assert data["node_timeline"]["node"]["status"] == "FAILED"
    assert data["failures"][0]["message"] == "actual cause"


def test_retry_limit_is_failed_not_waiting(monkeypatch):
    data = workflow_data("node")

    @task
    def exhausted(data, node_id):
        exhausted.retry(data, node_id)

    def retry(**kwargs):
        raise RuntimeError("retry limit reached")

    monkeypatch.setattr(exhausted.celery_task, "retry", retry)
    with pytest.raises(RuntimeError, match="retry limit reached"):
        exhausted(data, "node")
    assert timeline.read_timeline(data)["node"]["status"] == "FAILED"


def test_new_expanded_node_is_added_without_payload():
    data = workflow_data("parent")
    timeline.reset_run(data)
    timeline.initialize_timeline(data)
    expanded = workflow_data("expanded")["nodes"][0]
    expanded["data"]["title"] = "custom title" * 50
    expanded["data"]["template"]["password"] = {"value": "credential"}
    data["nodes"].append(expanded)
    timeline.update_timeline(data, "expanded", "RUNNING")
    result = timeline.read_timeline(data)
    assert set(result) == {"parent", "expanded"}
    assert len(result["expanded"]["title"]) == 200
    assert "credential" not in str(result)


def test_missing_run_id_stays_local_and_malformed_progress_does_not_stop_task(isolated_cache):
    data = workflow_data("node")
    data.pop("rid")
    data["node_timeline"] = ["old invalid progress"]

    @task
    def succeeded(data, node_id):
        return data

    result = succeeded(data, "node")
    assert result["node_timeline"]["node"]["status"] == "SUCCEEDED"
    assert list(isolated_cache.iterkeys()) == []


def test_skip_and_reset_clear_only_transient_fields():
    data = workflow_data("node")
    data.update(failures=[{}], error_task="old", skipped_nodes=["node"], node_run_time={"node": 4})
    data["nodes"][0]["run_time"] = 4
    data["nodes"][0]["data"]["status"] = 500
    data["nodes"][0]["data"]["template"]["api_key"] = {"value": "credential"}
    timeline.reset_run(data)
    assert not set(("failures", "error_task", "skipped_nodes", "node_run_time")) & data.keys()
    assert "status" not in data["nodes"][0]["data"] and "run_time" not in data["nodes"][0]
    assert data["nodes"][0]["data"]["template"]["api_key"]["value"] == "credential"
    assert "credential" not in str(data["node_timeline"])
    data["skipped_nodes"] = ["node"]

    @task
    def skipped(data, node_id):
        raise AssertionError("must not execute")

    skipped(data, "node")
    assert data["node_timeline"]["node"]["status"] == "SKIPPED"
    assert data["node_timeline"]["node"]["started_at"] is None
