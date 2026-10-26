from copy import deepcopy
from pathlib import Path

import pytest

from utilities import workflow_artifacts as artifacts


def node(identity="producer", kind="Document", **data):
    return {"id": identity, "type": kind, "data": data}


def test_registration_existing_files_only_and_source_deduplication(tmp_path):
    path = tmp_path / "report.txt"
    path.write_text("report", encoding="utf-8")
    data = {"nodes": [node(title="Report"), node("second")]}
    for value in (path, path, tmp_path, tmp_path / "absent", "https://example.com/report"):
        artifacts.register_artifact(data, "producer", value)
    artifacts.register_artifact(data, "second", path)
    rows = artifacts.get_run_artifacts(data)
    assert len(data["nodes"][0]["data"]["artifacts"]) == 1
    assert len(rows) == 1 and len(rows[0]["sources"]) == 2
    assert rows[0]["size"] == 6 and rows[0]["exists"] and rows[0]["parent_exists"]
    assert isinstance(rows[0]["created_at"], int)
    path.unlink()
    missing = artifacts.get_run_artifacts(data)[0]
    assert missing["exists"] is False and missing["size"] is None and missing["parent_exists"]


def test_legacy_outputs_require_execution_and_never_include_inputs(tmp_path):
    path = str(tmp_path / "legacy.txt")
    producer = node(template={"output": {"value": path}, "files": {"value": "https://example.com"}})
    data = {"nodes": [producer, node("text", "Text", status=200, template={"output": {"value": path}})]}
    assert artifacts.get_run_artifacts(data) == []
    producer["data"]["status"] = 200
    assert artifacts.get_run_artifacts(data)[0]["path"] == path
    producer["data"].pop("status")
    data["node_timeline"] = {"producer": {"status": "FAILED"}}
    assert artifacts.get_run_artifacts(data) == []
    data["node_timeline"]["producer"]["status"] = "SUCCEEDED"
    producer["data"]["artifacts"] = [{"path": str(tmp_path / "explicit.txt")}]
    assert artifacts.get_run_artifacts(data)[0]["name"] == "explicit.txt"
    producer["type"] = "DocumentConvert"
    producer["data"].pop("artifacts")
    producer["data"]["template"]["output"]["value"] = [path, "http://localhost/static/file.txt", "file:///etc/passwd"]
    assert len(artifacts.get_run_artifacts(data)) == 1
    producer["type"] = "ProgrammingFunction"
    producer["data"]["template"]["files"]["value"] = [[path]]
    assert len(artifacts.get_run_artifacts(data)) == 1


def test_metadata_failure_cannot_fail_execution():
    artifacts.register_artifact(None, "node", object())


def test_malformed_old_metadata_is_ignored(tmp_path):
    data = {"node_timeline": [None], "nodes": [None, node(data=None), node("legacy", status=500, template={"output": {"value": str(tmp_path / "old.txt")}})]}
    assert artifacts.get_run_artifacts(data) == []
    data["nodes"].extend([{"data": None}, node(artifacts=[None, "bad", {"path": str(tmp_path / "file"), "name": {}, "created_at": float("nan")}], title={})])
    row = artifacts.get_run_artifacts(data)[0]
    assert row["name"] == "file" and row["created_at"] is None
    assert row["sources"][0]["title"] == "" and row["sources"][0]["node_type"] == "Document"


@pytest.mark.parametrize("platform,command", [("win32", None), ("darwin", "open"), ("linux", "xdg-open")])
def test_native_open_is_run_scoped_and_rechecks_existence(tmp_path, monkeypatch, platform, command):
    path = tmp_path / "artifact.txt"
    path.write_text("data")
    data = {"nodes": [node()]}
    artifacts.register_artifact(data, "producer", path)
    calls = []
    monkeypatch.setattr(artifacts.sys, "platform", platform)
    monkeypatch.setattr(artifacts.os, "startfile", lambda value: calls.append(value), raising=False)
    monkeypatch.setattr(artifacts.subprocess, "Popen", lambda args, **kwargs: calls.append((args, kwargs)))
    assert artifacts.open_run_artifact(data, str(path), "open")[0] == 200
    assert calls == ([str(path)] if command is None else [([command, str(path)], {"shell": False})])
    for value in (str(tmp_path / "other.txt"), "https://example.com/file", "file:///etc/passwd", None):
        assert artifacts.open_run_artifact(data, value, "open")[0] in (400, 404)
    assert artifacts.open_run_artifact(data, str(path), "execute")[0] == 400
    path.unlink()
    assert artifacts.open_run_artifact(data, str(path), "open")[0] == 404
    assert artifacts.open_run_artifact(data, str(path), "folder")[0] == 200


def test_fresh_reset_clears_own_and_related_artifacts_preserving_history_and_inputs(monkeypatch):
    from utilities.workflow_timeline import reset_run
    from test_workflow_failures import workflow_data

    data = workflow_data("node")
    data["nodes"][0]["data"].update(artifacts=[{"path": "/old"}], template={"files": {"value": "input"}})
    data["related_workflows"] = {"related": deepcopy(data)}
    history = deepcopy(data)
    reset_run(data)
    assert data["nodes"][0]["data"]["artifacts"] == []
    assert data["related_workflows"]["related"]["nodes"][0]["data"]["artifacts"] == []
    assert data["nodes"][0]["data"]["template"]["files"]["value"] == "input"
    assert history["nodes"][0]["data"]["artifacts"]
    data["nodes"][0]["type"] = "Document"
    data["nodes"][0]["data"].update(status=500, template={"output": {"value": str(Path.cwd() / "old.txt")}})
    assert artifacts.get_run_artifacts(data) == []


def test_api_access_and_active_finished_nodes(tmp_path, monkeypatch):
    from api import workflow_api
    from models import WorkflowRunRecord
    from uuid import uuid4

    path = tmp_path / "live.txt"
    path.write_text("live")
    finished = {"nodes": [node(status=200)]}
    artifacts.register_artifact(finished, "producer", path)
    record = WorkflowRunRecord(rid=uuid4(), status="RUNNING", data={"nodes": [node()]})
    monkeypatch.setattr(workflow_api, "get_user_object_general", lambda *args, **kwargs: (200, "", record))
    class Cache:
        def get(self, key, default):
            return finished["nodes"] if "finished_nodes" in key else default
    monkeypatch.setattr(workflow_api, "cache", Cache())
    api = workflow_api.WorkflowRunRecordAPI()
    assert api.list_artifacts({"rid": record.rid.hex})["data"]["artifacts"][0]["path"] == str(path)
    from api import API
    bridge = API()
    bridge.add_apis(workflow_api.WorkflowRunRecordAPI)
    assert bridge.workflow_run_record__list_artifacts({"rid": record.rid.hex})["data"]["artifacts"][0]["path"] == str(path)
    assert api.open_artifact({"rid": record.rid.hex, "path": str(tmp_path / "other"), "action": "open"})["status"] == 404
    monkeypatch.setattr(workflow_api, "get_user_object_general", lambda *args, **kwargs: (403, "Forbidden", None))
    assert api.list_artifacts({})["status"] == api.open_artifact({})["status"] == 403
