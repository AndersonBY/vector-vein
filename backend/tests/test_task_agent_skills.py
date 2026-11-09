from __future__ import annotations

import os
import sqlite3
import subprocess
import zipfile
from pathlib import Path

import pytest

from task_agent.service import TaskConflict
from task_agent.skills import (
    MAX_SKILL_ARCHIVE_MEMBERS,
    MAX_SKILL_FILE_BYTES,
    MAX_SKILL_FILES,
    SkillLibraryError,
    SkillsLibrary,
    _validate_relative_posix_path,
)
from task_agent.store import BusinessStore, SCHEMA_VERSION


def valid_skill_md(
    name: str = "report-helper",
    description: str = "Generate structured verification reports.",
    body: str = "# Report Helper\n\nFollow the template in `references/guide.md`.",
    extra_frontmatter: str = 'license: MIT\ncompatibility: ">=0.33"\nallowed-tools: read_file write_file\nmetadata:\n  owner: qa\n',
) -> str:
    return f"---\nname: {name}\ndescription: {description}\n{extra_frontmatter}---\n\n{body}\n"


def test_store_schema_v7_and_skill_create_reload_edit_and_delete_preserves_revisions(tmp_path):
    task_root = tmp_path / "task-agent"
    lib = SkillsLibrary(task_root)
    with lib.store.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION

    created = lib.save(
        {
            "skill_id": "skill_report",
            "content": valid_skill_md(body="Version 1 body"),
            "enabled": True,
        }
    )
    assert created["skill_id"] == "skill_report"
    assert created["name"] == "report-helper"
    assert created["description"] == "Generate structured verification reports."
    assert created["license"] == "MIT"
    assert created["compatibility"] == ">=0.33"
    assert created["allowed_tools"] == "read_file write_file"
    assert created["metadata"] == {"owner": "qa"}
    assert created["version"] == 1
    assert created["enabled"] is True
    assert created["instructions"] == "Version 1 body"
    assert [f["path"] for f in created["files"]] == ["SKILL.md"]

    rev1 = lib.get_revision("skill_report", 1)
    rev1_md = Path(rev1["bundle_path"]) / "SKILL.md"
    assert rev1_md.read_text(encoding="utf-8") == created["content"]

    same = lib.save(
        {
            "skill_id": "skill_report",
            "content": valid_skill_md(body="Version 1 body"),
            "expected_updated_at": created["updated_at"],
        }
    )
    assert same["version"] == 1

    disabled = lib.save(
        {
            "skill_id": "skill_report",
            "enabled": False,
            "expected_updated_at": created["updated_at"],
        }
    )
    assert disabled["enabled"] is False
    assert disabled["version"] == 1

    updated = lib.save(
        {
            "skill_id": "skill_report",
            "content": valid_skill_md(body="Version 2 body"),
            "enabled": True,
            "expected_updated_at": disabled["updated_at"],
        }
    )
    assert updated["version"] == 2
    assert updated["enabled"] is True
    assert updated["instructions"] == "Version 2 body"
    assert rev1_md.read_text(encoding="utf-8") == created["content"]
    assert lib.preview("skill_report", "SKILL.md", version=1)["text"] == created["content"]
    assert lib.preview("skill_report", "SKILL.md", version=2)["text"] == updated["content"]

    with pytest.raises(TaskConflict):
        lib.save(
            {
                "skill_id": "skill_report",
                "content": valid_skill_md(body="Stale write"),
                "expected_updated_at": created["updated_at"],
            }
        )

    reloaded = SkillsLibrary(task_root, store=BusinessStore(task_root / "tasks.db"))
    assert [item["skill_id"] for item in reloaded.list(search="report")] == ["skill_report"]
    assert reloaded.list(search="nonexistent") == []
    assert reloaded.get("skill_report")["version"] == 2

    assert reloaded.delete("skill_report", expected_updated_at=updated["updated_at"]) == {
        "deleted": True,
        "skill_id": "skill_report",
    }
    assert reloaded.list() == []
    with pytest.raises(KeyError):
        reloaded.get("skill_report")
    assert reloaded.get_revision("skill_report", 1)["version"] == 1
    assert reloaded.get_revision("skill_report", 2)["version"] == 2
    assert reloaded.preview("skill_report", "SKILL.md", version=1)["text"] == created["content"]
    assert reloaded.files("skill_report", version=2)["files"][0]["path"] == "SKILL.md"


def test_real_schema6_upgrade_preserves_existing_tasks_and_projects(tmp_path):
    db_path = tmp_path / "upgrade_v6.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE tasks (
                tid TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                goal TEXT NOT NULL,
                status TEXT NOT NULL,
                current_turn_id TEXT,
                model_provider TEXT NOT NULL,
                model TEXT NOT NULL,
                reasoning_effort TEXT NOT NULL,
                config_snapshot TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                project_id TEXT
            );
            CREATE TABLE messages (
                mid TEXT PRIMARY KEY,
                task_id TEXT NOT NULL REFERENCES tasks(tid) ON DELETE CASCADE,
                turn_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL,
                attachments TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(task_id, turn_id, role)
            );
            CREATE TABLE task_projection (
                task_id TEXT PRIMARY KEY REFERENCES tasks(tid), cursor TEXT, state TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE task_events (
                task_id TEXT NOT NULL REFERENCES tasks(tid), event_id TEXT NOT NULL,
                seq INTEGER NOT NULL, ordinal INTEGER NOT NULL, data TEXT NOT NULL,
                PRIMARY KEY(task_id, event_id)
            );
            CREATE TABLE task_commands (
                task_id TEXT NOT NULL REFERENCES tasks(tid), command_id TEXT NOT NULL,
                method TEXT NOT NULL, params TEXT NOT NULL, receipt TEXT,
                PRIMARY KEY(task_id, command_id)
            );
            CREATE TABLE task_agent_profiles (
                agent_id TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE task_workflow_jobs (
                job_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(tid),
                run_id TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, result TEXT
            );
            CREATE TABLE task_model_failures (
                task_id TEXT NOT NULL REFERENCES tasks(tid), call_id TEXT NOT NULL, data TEXT NOT NULL,
                PRIMARY KEY(task_id, call_id)
            );
            CREATE TABLE task_risk_reviews (
                task_id TEXT NOT NULL REFERENCES tasks(tid), request_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL, data TEXT NOT NULL,
                PRIMARY KEY(task_id, request_id)
            );
            CREATE TABLE task_projects (
                project_id TEXT PRIMARY KEY, name TEXT NOT NULL, roots TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            INSERT INTO task_projects VALUES ('p1', 'Proj', '["C:/work"]', 't0', 't0');
            INSERT INTO tasks VALUES ('t1', 't1', 'Title', 'Goal', 'COMPLETED', NULL, 'mock', 'mock', 'default', '{}', 't0', 't0', 'p1');
            PRAGMA user_version=6;
            """
        )
        conn.commit()
    finally:
        conn.close()

    store = BusinessStore(db_path)
    with store.connect() as check_conn:
        assert check_conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert store.get_project("p1")["name"] == "Proj"
    assert store.get_task("t1")["title"] == "Title"
    lib = SkillsLibrary(tmp_path, store=store)
    saved = lib.save({"skill_id": "upgraded_skill", "content": valid_skill_md()})
    assert saved["version"] == 1


def test_directory_and_archive_imports_preserve_source_and_unicode_resources(tmp_path):
    task_root = tmp_path / "task-agent"
    lib = SkillsLibrary(task_root)

    source_dir = tmp_path / "external_source" / "data-cleaner"
    (source_dir / "scripts").mkdir(parents=True)
    (source_dir / "references" / "中文文档").mkdir(parents=True)
    (source_dir / "assets").mkdir(parents=True)
    original_md = valid_skill_md(name="data-cleaner", description="Clean tabular datasets.")
    (source_dir / "SKILL.md").write_text(original_md, encoding="utf-8", newline="\n")
    (source_dir / "scripts" / "clean.py").write_text("print('v1')\n", encoding="utf-8", newline="\n")
    (source_dir / "references" / "guide.md").write_text("# Guide v1\n", encoding="utf-8", newline="\n")
    (source_dir / "references" / "中文文档" / "说明.md").write_text("# 中文说明\n", encoding="utf-8", newline="\n")
    (source_dir / "assets" / "schema.json").write_text('{"v": 1}\n', encoding="utf-8", newline="\n")

    imported = lib.import_path({"skill_id": "cleaner", "path": str(source_dir)})
    assert imported["version"] == 1
    assert imported["source_kind"] == "directory"
    assert {f["path"] for f in imported["files"]} == {
        "SKILL.md",
        "assets/schema.json",
        "references/guide.md",
        "references/中文文档/说明.md",
        "scripts/clean.py",
    }
    assert lib.preview("cleaner", "references/中文文档/说明.md")["text"] == "# 中文说明\n"

    (source_dir / "references" / "guide.md").write_text("# Guide mutated in source\n", encoding="utf-8", newline="\n")
    (source_dir / "scripts" / "clean.py").unlink()
    assert lib.preview("cleaner", "references/guide.md")["text"] == "# Guide v1\n"
    assert lib.preview("cleaner", "scripts/clean.py")["text"] == "print('v1')\n"

    edited = lib.save(
        {
            "skill_id": "cleaner",
            "content": valid_skill_md(name="data-cleaner", description="Updated description.", body="Updated instructions"),
            "expected_updated_at": imported["updated_at"],
        }
    )
    assert edited["version"] == 2
    assert {f["path"] for f in edited["files"]} == {
        "SKILL.md",
        "assets/schema.json",
        "references/guide.md",
        "references/中文文档/说明.md",
        "scripts/clean.py",
    }
    assert lib.preview("cleaner", "SKILL.md", version=1)["text"] == original_md
    assert lib.preview("cleaner", "references/guide.md", version=2)["text"] == "# Guide v1\n"

    archive_path = tmp_path / "wrapped.skill"
    with zipfile.ZipFile(archive_path, "w") as zf:
        zf.writestr("archive-skill/SKILL.md", valid_skill_md(name="archive-skill", description="From archive"))
        zf.writestr("archive-skill/references/notes.txt", "archive note")
    from_archive = lib.import_path({"skill_id": "archived", "path": str(archive_path)})
    assert from_archive["name"] == "archive-skill"
    assert from_archive["source_kind"] == "archive"
    assert lib.preview("archived", "references/notes.txt")["text"] == "archive note"
    assert archive_path.is_file()


def test_windows_path_alias_overwrite_and_reserved_names_rejected(tmp_path):
    lib = SkillsLibrary(tmp_path / "task-agent")

    # Actual two-file ZIP with SKILL.md (VISIBLE_BENIGN) and SKILL.md. (HIDDEN_ALTERNATE).
    alias_zip = tmp_path / "alias_overwrite.zip"
    with zipfile.ZipFile(alias_zip, "w") as zf:
        zf.writestr("SKILL.md", valid_skill_md(body="VISIBLE_BENIGN"))
        zf.writestr("SKILL.md.", valid_skill_md(body="HIDDEN_ALTERNATE"))

    with pytest.raises(SkillLibraryError) as exc:
        lib.import_path({"skill_id": "alias_attack", "path": str(alias_zip)})
    assert exc.value.code == "invalid_path"
    assert lib.list() == []
    with pytest.raises(KeyError):
        lib.get("alias_attack")

    # Test trailing dots, trailing spaces, leading spaces, DOS device names with & without extensions, control chars.
    bad_paths = [
        "SKILL.md.",
        "references/notes.txt ",
        "references/ notes.txt",
        "references.../notes.txt",
        "assets/CON",
        "assets/con.txt",
        "assets/PRN.md",
        "assets/aux.txt",
        "assets/nul",
        "assets/COM1.json",
        "assets/lpt9.tar.gz",
        "assets/COM\u00b9.txt",
        "assets/LPT\u00b3",
        "assets/bad<name>.txt",
        "assets/bad|name.txt",
        "assets/bad\x01name.txt",
        "assets/sub//file.txt",
    ]
    for bad in bad_paths:
        with pytest.raises(SkillLibraryError) as path_exc:
            _validate_relative_posix_path(bad)
        assert path_exc.value.code == "invalid_path"

        zpath = tmp_path / "bad_member.zip"
        with zipfile.ZipFile(zpath, "w") as zf:
            zf.writestr("SKILL.md", valid_skill_md())
            zf.writestr(bad, "payload")
        with pytest.raises(SkillLibraryError):
            lib.import_path({"skill_id": "bad_member", "path": str(zpath)})
    assert lib.list() == []


def test_sql_publication_failure_cleans_up_new_revision_and_allows_retry_while_preserving_old_revisions(tmp_path):
    lib = SkillsLibrary(tmp_path / "task-agent")

    with lib.store.connect() as conn:
        conn.execute(
            "CREATE TRIGGER fail_skill_insert BEFORE INSERT ON task_skills "
            "BEGIN SELECT RAISE(ABORT,'synthetic failure'); END"
        )

    with pytest.raises(sqlite3.IntegrityError, match="synthetic failure"):
        lib.save({"skill_id": "retry_me", "content": valid_skill_md(body="First attempt")})

    assert lib.list() == []
    with pytest.raises(KeyError):
        lib.get_revision("retry_me", 1)
    assert not (lib.skills_root / "retry_me" / "rev_1").exists()

    with lib.store.connect() as conn:
        conn.execute("DROP TRIGGER fail_skill_insert")

    # Retry succeeds cleanly after trigger removal.
    saved_v1 = lib.save({"skill_id": "retry_me", "content": valid_skill_md(body="First attempt")})
    assert saved_v1["version"] == 1
    rev1_file = Path(lib.get_revision("retry_me", 1)["bundle_path"]) / "SKILL.md"
    assert rev1_file.is_file()

    # Now fail an update to v2 via BEFORE UPDATE trigger and verify v1 remains intact and v2 is cleaned up.
    with lib.store.connect() as conn:
        conn.execute(
            "CREATE TRIGGER fail_skill_update BEFORE UPDATE ON task_skills "
            "BEGIN SELECT RAISE(ABORT,'synthetic update failure'); END"
        )

    with pytest.raises(sqlite3.IntegrityError, match="synthetic update failure"):
        lib.save(
            {
                "skill_id": "retry_me",
                "content": valid_skill_md(body="Second attempt"),
                "expected_updated_at": saved_v1["updated_at"],
            }
        )

    assert lib.get("retry_me")["version"] == 1
    assert rev1_file.is_file()
    assert rev1_file.read_text(encoding="utf-8") == saved_v1["content"]
    with pytest.raises(KeyError):
        lib.get_revision("retry_me", 2)
    assert not (lib.skills_root / "retry_me" / "rev_2").exists()

    with lib.store.connect() as conn:
        conn.execute("DROP TRIGGER fail_skill_update")

    saved_v2 = lib.save(
        {
            "skill_id": "retry_me",
            "content": valid_skill_md(body="Second attempt"),
            "expected_updated_at": saved_v1["updated_at"],
        }
    )
    assert saved_v2["version"] == 2
    assert rev1_file.read_text(encoding="utf-8") == saved_v1["content"]


def test_bounded_directory_reads_and_archive_member_header_limits(tmp_path, monkeypatch):
    lib = SkillsLibrary(tmp_path / "task-agent")

    # 1. File whose actual read bytes exceed MAX_SKILL_FILE_BYTES even if stat reported a small size.
    grow_dir = tmp_path / "grow-skill"
    grow_dir.mkdir()
    (grow_dir / "SKILL.md").write_text(valid_skill_md(name="grow-skill"), encoding="utf-8")
    growing_file = grow_dir / "data.bin"
    growing_file.write_bytes(b"x" * (MAX_SKILL_FILE_BYTES + 10))

    real_stat = Path.stat

    def fake_stat(self, *args, **kwargs):
        st = real_stat(self, *args, **kwargs)
        if self == growing_file:
            class SmallStat:
                st_mode = st.st_mode
                st_size = 100
                st_mtime = st.st_mtime
            return SmallStat()
        return st

    monkeypatch.setattr(Path, "stat", fake_stat)
    with pytest.raises(SkillLibraryError) as exc:
        lib.import_path({"skill_id": "grow", "path": str(grow_dir)})
    assert exc.value.code == "file_too_large"
    monkeypatch.undo()

    # 2. Actual aggregate bytes across multiple files exceeding MAX_SKILL_TOTAL_BYTES.
    total_dir = tmp_path / "total-skill"
    total_dir.mkdir()
    (total_dir / "SKILL.md").write_text(valid_skill_md(name="total-skill"), encoding="utf-8")
    chunk_size = (MAX_SKILL_FILE_BYTES // 2) + 100_000
    for idx in range(10):
        (total_dir / f"part_{idx}.bin").write_bytes(b"y" * chunk_size)
    with pytest.raises(SkillLibraryError) as exc2:
        lib.import_path({"skill_id": "total_exceeded", "path": str(total_dir)})
    assert exc2.value.code == "bundle_too_large"

    # 3. Pathological archive with excessive empty directory headers exceeding MAX_SKILL_ARCHIVE_MEMBERS.
    many_headers_zip = tmp_path / "many_headers.zip"
    with zipfile.ZipFile(many_headers_zip, "w") as zf:
        zf.writestr("SKILL.md", valid_skill_md())
        for idx in range(MAX_SKILL_ARCHIVE_MEMBERS + 1):
            zf.writestr(f"empty_{idx}/", "")
    with pytest.raises(SkillLibraryError) as exc3:
        lib.import_path({"skill_id": "many_headers", "path": str(many_headers_zip)})
    assert exc3.value.code == "too_many_files"


@pytest.mark.parametrize(
    "bad_content",
    [
        "No frontmatter at all",
        "---\nname: Invalid_Uppercase\ndescription: bad name\n---\nBody",
        "---\nname: -leading-hyphen\ndescription: bad name\n---\nBody",
        "---\nname: double--hyphen\ndescription: bad name\n---\nBody",
        "---\nname: valid-name\n---\nMissing description",
        "---\nname: valid-name\ndescription: valid\nunknown_field: disallowed\n---\nBody",
    ],
)
def test_invalid_frontmatter_and_strict_sdk_validation_rejected(tmp_path, bad_content):
    lib = SkillsLibrary(tmp_path / "task-agent")
    with pytest.raises(SkillLibraryError):
        lib.save({"skill_id": "bad", "content": bad_content})
    assert lib.list() == []


def test_archive_traversal_duplicates_symlinks_and_oversize_rejected(tmp_path):
    lib = SkillsLibrary(tmp_path / "task-agent")

    traversal_zip = tmp_path / "traversal.zip"
    with zipfile.ZipFile(traversal_zip, "w") as zf:
        zf.writestr("SKILL.md", valid_skill_md())
        zf.writestr("../escape.txt", "escaped")
    with pytest.raises(SkillLibraryError) as exc:
        lib.import_path({"skill_id": "bad1", "path": str(traversal_zip)})
    assert exc.value.code == "invalid_path"

    collision_zip = tmp_path / "collision.zip"
    with zipfile.ZipFile(collision_zip, "w") as zf:
        zf.writestr("SKILL.md", valid_skill_md())
        zf.writestr("references/Guide.md", "one")
        zf.writestr("references/guide.md", "two")
    with pytest.raises(SkillLibraryError) as exc:
        lib.import_path({"skill_id": "bad2", "path": str(collision_zip)})
    assert exc.value.code == "duplicate_entry"

    symlink_zip = tmp_path / "symlink.zip"
    with zipfile.ZipFile(symlink_zip, "w") as zf:
        zf.writestr("SKILL.md", valid_skill_md())
        info = zipfile.ZipInfo("references/link.md")
        info.create_system = 3
        info.external_attr = (0o120777 & 0xFFFF) << 16
        zf.writestr(info, "/etc/passwd")
    with pytest.raises(SkillLibraryError) as exc:
        lib.import_path({"skill_id": "bad3", "path": str(symlink_zip)})
    assert exc.value.code == "symlink_rejected"

    many_zip = tmp_path / "many.zip"
    with zipfile.ZipFile(many_zip, "w") as zf:
        zf.writestr("SKILL.md", valid_skill_md())
        for idx in range(MAX_SKILL_FILES):
            zf.writestr(f"references/f_{idx}.txt", "x")
    with pytest.raises(SkillLibraryError) as exc:
        lib.import_path({"skill_id": "bad4", "path": str(many_zip)})
    assert exc.value.code == "too_many_files"

    huge_dir = tmp_path / "huge-skill"
    huge_dir.mkdir()
    (huge_dir / "SKILL.md").write_text(valid_skill_md(name="huge-skill"), encoding="utf-8")
    (huge_dir / "big.bin").write_bytes(b"a" * (MAX_SKILL_FILE_BYTES + 1))
    with pytest.raises(SkillLibraryError) as exc:
        lib.import_path({"skill_id": "bad5", "path": str(huge_dir)})
    assert exc.value.code == "file_too_large"


def test_committed_revision_survives_response_build_failure(tmp_path, monkeypatch):
    lib = SkillsLibrary(tmp_path / "task-agent")
    content = valid_skill_md(body="Committed instructions")

    def fail_view(_skill):
        raise RuntimeError("synthetic response failure")

    with monkeypatch.context() as context:
        context.setattr(lib, "_detail_view", fail_view)
        with pytest.raises(RuntimeError, match="synthetic response failure"):
            lib.save({"skill_id": "committed", "content": content})

    committed = lib.store.get_skill("committed")
    assert committed is not None
    assert (Path(committed["bundle_path"]) / "SKILL.md").is_file()
    assert lib.save({"skill_id": "committed", "content": content})["version"] == 1


def test_missing_import_source_reports_file_not_found_and_reparse_points_rejected(tmp_path):
    lib = SkillsLibrary(tmp_path / "task-agent")

    # Missing source path raises FileNotFoundError rather than symlink_rejected.
    with pytest.raises(FileNotFoundError):
        lib.import_path({"skill_id": "missing_src", "path": str(tmp_path / "does_not_exist" / "SKILL.md")})

    target_dir = tmp_path / "real_target"
    target_dir.mkdir()
    (target_dir / "SKILL.md").write_text(valid_skill_md(name="real-target"), encoding="utf-8")

    skill_with_junction = tmp_path / "junction-skill"
    skill_with_junction.mkdir()
    (skill_with_junction / "SKILL.md").write_text(valid_skill_md(name="junction-skill"), encoding="utf-8")
    junction_path = skill_with_junction / "linked"
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(junction_path), str(target_dir)], check=True, capture_output=True)
    else:
        junction_path.symlink_to(target_dir, target_is_directory=True)
    try:
        with pytest.raises(SkillLibraryError) as exc:
            lib.import_path({"skill_id": "junc", "path": str(skill_with_junction)})
        assert exc.value.code == "symlink_rejected"
        # Also reject importing directly through a junction or symlink ancestor path.
        with pytest.raises(SkillLibraryError) as exc_anc:
            lib.import_path({"skill_id": "junc_anc", "path": str(junction_path / "SKILL.md")})
        assert exc_anc.value.code == "symlink_rejected"
    finally:
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "rmdir", str(junction_path)], check=False, capture_output=True)
        else:
            junction_path.unlink()

    lib.save({"skill_id": "safe", "content": valid_skill_md()})
    for bad_path in ("../SKILL.md", "/SKILL.md", "SKILL.md:stream", "references\\guide.md", ".vv-agent/secret", "SKILL.md.", "CON.txt"):
        with pytest.raises(SkillLibraryError):
            lib.preview("safe", bad_path)
