from pathlib import Path

import pytest

import task_agent.skills as skills_module
from task_agent.skills import MAX_SKILL_MD_BYTES, SkillsLibrary


def make_skill(folder, name="local-helper", *, content=None):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(content or f"---\nname: {name}\ndescription: A local helper.\n---\n\nInstructions.\n", encoding="utf-8")
    return folder


@pytest.fixture
def local_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    return home


def test_local_discovery_only_scans_known_immediate_folders_and_does_not_import(tmp_path, local_home):
    first = make_skill(local_home / ".agents/skills/helper")
    (first / "reference.txt").write_text("retained reference", encoding="utf-8")
    make_skill(local_home / ".codex/skills/other", name="other-helper")
    make_skill(local_home / ".agents/skills/group/nested", name="not-discovered")
    make_skill(local_home / ".codex/skills/.system/internal", name="not-discovered")
    make_skill(local_home / ".unrelated/skills/hidden", name="not-discovered")
    library = SkillsLibrary(tmp_path / "tasks")
    before = {p: p.read_bytes() for p in local_home.rglob("*") if p.is_file()}

    result = library.local_skills()

    assert [root["id"] for root in result["roots"]] == [".agents", ".codex", ".claude"]
    assert [root["status"] for root in result["roots"]] == ["ready", "ready", "missing"]
    assert {row["name"] for row in result["skills"]} == {"local-helper", "other-helper"}
    assert all(not row["error_code"] for row in result["skills"])
    assert result["truncated"] is False
    assert library.list() == []
    assert before == {p: p.read_bytes() for p in local_home.rglob("*") if p.is_file()}

    imported = library.import_path({"skill_id": "from_local", "path": result["skills"][0]["path"]})
    assert imported["name"] == "local-helper"
    assert [item["path"] for item in imported["files"]] == ["SKILL.md", "reference.txt"]
    assert (first / "reference.txt").read_text(encoding="utf-8") == "retained reference"


def test_invalid_metadata_and_oversized_skill_do_not_hide_other_sources(tmp_path, local_home):
    root = local_home / ".agents/skills"
    make_skill(root / "missing-description", content="---\nname: missing-description\n---\nBody")
    make_skill(root / "invalid-yaml", content="---\nname: [\n---\nBody")
    make_skill(root / "too-large", content="x" * (MAX_SKILL_MD_BYTES + 1))
    invalid_utf = make_skill(root / "invalid-utf")
    (invalid_utf / "SKILL.md").write_bytes(b"\xff")
    make_skill(local_home / ".claude/skills/good", name="good-helper")
    rows = SkillsLibrary(tmp_path / "tasks").local_skills()["skills"]
    by_folder = {Path(row["path"]).name: row for row in rows}
    assert by_folder["missing-description"]["error_code"] == "invalid_frontmatter"
    assert by_folder["invalid-yaml"]["error_code"] == "invalid_frontmatter"
    assert by_folder["too-large"]["error_code"] == "file_too_large"
    assert by_folder["invalid-utf"]["error_code"] == "invalid_encoding"
    assert by_folder["good"]["name"] == "good-helper"


def test_scan_entry_and_byte_limits_are_explicit(tmp_path, local_home, monkeypatch):
    for index in range(4):
        make_skill(local_home / f".agents/skills/helper-{index}", name=f"helper-{index}")
    monkeypatch.setattr(skills_module, "MAX_LOCAL_SKILL_ENTRIES", 2)
    result = SkillsLibrary(tmp_path / "tasks").local_skills()
    assert result["truncated"] is True
    assert result["roots"][0]["status"] == "limited"
    assert len(result["skills"]) == 2
    monkeypatch.setattr(skills_module, "MAX_LOCAL_SKILL_ENTRIES", 512)
    monkeypatch.setattr(skills_module, "MAX_LOCAL_SKILL_SCAN_BYTES", 10)
    result = SkillsLibrary(tmp_path / "tasks").local_skills()
    assert result["truncated"] is True
    assert result["skills"][0]["error_code"] == "bundle_too_large"


def test_unreadable_root_is_reported_without_discarding_other_roots(tmp_path, local_home, monkeypatch):
    blocked = local_home / ".codex/skills"
    blocked.mkdir(parents=True)
    make_skill(local_home / ".claude/skills/good")
    real_scandir = skills_module.os.scandir

    def scandir(path):
        if Path(path) == blocked:
            raise PermissionError("private filesystem detail")
        return real_scandir(path)

    monkeypatch.setattr(skills_module.os, "scandir", scandir)
    result = SkillsLibrary(tmp_path / "tasks").local_skills()
    assert result["roots"][1]["status"] == "unavailable"
    assert len(result["skills"]) == 1
    assert "private filesystem detail" not in str(result)


def test_common_installation_links_are_resolved_deduplicated_and_importable(tmp_path, local_home):
    target = make_skill(tmp_path / "shared/helper")
    for agent in (".agents", ".codex"):
        folder = local_home / agent / "skills"
        folder.mkdir(parents=True)
        try:
            (folder / "helper").symlink_to(target, target_is_directory=True)
        except OSError:
            pytest.skip("Creating symlinks requires local OS support")
    library = SkillsLibrary(tmp_path / "tasks")
    result = library.local_skills()
    assert len(result["skills"]) == 1
    assert result["skills"][0]["sources"] == [".agents", ".codex"]
    assert result["skills"][0]["path"] == str(target.resolve())
    imported = library.import_path({"skill_id": "linked_install", "path": result["skills"][0]["path"]})
    assert imported["version"] == 1


def test_linked_instruction_file_remains_rejected(tmp_path, local_home):
    target = make_skill(tmp_path / "shared/helper")
    folder = local_home / ".agents/skills/linked-md"
    folder.mkdir(parents=True)
    try:
        (folder / "SKILL.md").symlink_to(target / "SKILL.md")
    except OSError:
        pytest.skip("Creating symlinks requires local OS support")
    row = SkillsLibrary(tmp_path / "tasks").local_skills()["skills"][0]
    assert row["error_code"] == "symlink_rejected"


def test_local_skills_api_returns_the_real_discovery_projection(tmp_path, local_home, monkeypatch):
    from api.task_agent_api import TaskAgentAPI
    import api.task_agent_api as api_module

    make_skill(local_home / ".agents/skills/helper")
    library = SkillsLibrary(tmp_path / "tasks")
    monkeypatch.setattr(api_module, "task_agent_service", lambda: library)
    response = TaskAgentAPI().local_skills({})
    assert response["status"] == 200
    assert response["data"]["skills"][0]["name"] == "local-helper"
    assert response["data"]["roots"][0]["label"] == "~/.agents/skills"
