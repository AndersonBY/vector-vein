from types import SimpleNamespace

import pytest

from knowledge_base import KnowledgeService
from knowledge_base.storage import KnowledgeError
from task_agent.files import list_files, open_file, preview_file, workspace_file


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    kb = KnowledgeService(tmp_path / "knowledge", vector_store=SimpleNamespace(close=lambda: None), start_worker=False)
    base = kb.create("Notes", "test", "test", embedding_dimensions=3)
    other = kb.create("Private", "test", "test", embedding_dimensions=3)
    with kb._write():
        kb._insert_item(base["id"], None, "report.pdf", "file", text="正文" * 70000)
        kb._insert_item(other["id"], None, "secret.pdf", "file", text="PRIVATE")
    roots = [tmp_path / "first", tmp_path / "second"]
    for root in roots:
        root.mkdir()
        (root / "same.md").write_text(root.name, encoding="utf-8")
    snapshot = {"project": {"id": "p", "roots": [str(root) for root in roots]},
                "knowledge_bases": [{"kb_id": base["id"], "name": "Notes"}],
                "agent_profile": {"knowledge_base_ids": [base["id"]]}}
    store = SimpleNamespace(get_task=lambda tid: {"config_snapshot": snapshot},
                            get_project=lambda pid: snapshot["project"])
    service = SimpleNamespace(store=store, task_root=tmp_path)
    monkeypatch.setattr("knowledge_base.knowledge_service", lambda: kb)
    yield service, snapshot, kb
    kb.close()


def test_virtual_pdf_preview_and_revoked_mount(workspace):
    service, snapshot, _ = workspace
    result = preview_file(service, "task", ".knowledge/Notes/report.pdf")
    assert result == {"kind": "text", "text": ("正文" * 70000)[:131072],
                      "path": ".knowledge/Notes/report.pdf", "read_only": True,
                      "markdown": False, "truncated": True}
    snapshot["knowledge_bases"] = []
    snapshot["agent_profile"]["knowledge_base_ids"] = []
    with pytest.raises(ValueError, match="No knowledge"):
        preview_file(service, "task", ".knowledge/Notes/report.pdf")
    assert not any(file.get("read_only") for file in list_files(service, "task")["files"])


def test_roots_project_scope_and_normal_files(workspace):
    service, _, _ = workspace
    first = list_files(service, "task")
    virtual = [file for file in first["files"] if file.get("read_only")]
    assert len(virtual) == 1
    assert virtual[0] == {"path": ".knowledge/Notes/report.pdf", "relative_path": ".knowledge/Notes/report.pdf",
                          "root_id": "0", "name": "report.pdf", "size": None,
                          "modified_at": virtual[0]["modified_at"], "can_open": False, "read_only": True}
    assert not any(file.get("read_only") for file in list_files(service, "task", "1")["files"])
    assert not any(file.get("read_only") for file in list_files(service, None, project_id="p")["files"])
    assert preview_file(service, "task", "project-files/0/same.md")["text"] == "first"
    assert preview_file(service, "task", "project-files/1/same.md")["text"] == "second"
    with pytest.raises(ValueError, match="require a task"):
        preview_file(service, None, ".knowledge/Notes/report.pdf", project_id="p")


def test_nonproject_inputs_and_outputs_stay_local(workspace):
    service, snapshot, _ = workspace
    snapshot.pop("project")
    root = service.task_root / "workspaces" / "task"
    for folder in ("inputs", "outputs"):
        (root / folder).mkdir(parents=True)
        (root / folder / "note.md").write_text(folder, encoding="utf-8")
        assert preview_file(service, "task", f"{folder}/note.md")["text"] == folder
    result = list_files(service, "task")
    assert {row["path"] for row in result["files"]} == {
        "inputs/note.md", "outputs/note.md", ".knowledge/Notes/report.pdf"}
    assert next(row for row in result["files"] if row["path"] == "inputs/note.md")["is_input"]


@pytest.mark.parametrize("path", [
    ".knowledge/Notes/report.pdf", ".knowledge/../same.md", ".knowledge\\Notes\\report.pdf",
    "project-files/0/.knowledge/Notes/report.pdf", "project-files/1/.knowledge/Notes/report.pdf",
    "%2eknowledge/Notes/report.pdf",
    "./.knowledge/Notes/report.pdf", ".Knowledge/Notes/report.pdf",
    ".knowledge./Notes/report.pdf", ".knowledge /Notes/report.pdf",
])
def test_reserved_paths_never_reach_disk_or_native_open(workspace, path):
    service, _, _ = workspace
    with pytest.raises(ValueError):
        workspace_file(service, "task", path)
    for reveal in (True, False):
        with pytest.raises(ValueError):
            open_file(service, "task", path, reveal)
    if path != ".knowledge/Notes/report.pdf":
        with pytest.raises((ValueError, KnowledgeError)):
            preview_file(service, "task", path)


def test_single_vfs_page_and_combined_limit(workspace, monkeypatch):
    service, _, _ = workspace
    calls = []

    def listing(kb, mounts, args):
        calls.append(args)
        return {"entries": [{"kind": "file", "path": f".knowledge/Notes/{i}.pdf", "name": f"{i}.pdf",
                             "modified_at": 0, "size": 12} for i in range(1000)],
                "next_offset": 1000, "truncated": True}

    monkeypatch.setattr("knowledge_base.virtual.virtual_operation", listing)
    result = list_files(service, "task")
    assert len(result["files"]) == 1000
    assert result["limited"] is True
    assert calls == [{"action": "list", "path": ".knowledge", "limit": 1000, "recursive": True}]
