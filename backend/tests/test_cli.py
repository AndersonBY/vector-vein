from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path
import zipfile

import pytest


CLI = Path(__file__).resolve().parents[1] / "cli.py"


def command(workspace, *arguments, expected=0):
    result = subprocess.run([sys.executable, "-X", "utf8", str(CLI), "--workspace", str(workspace), *map(str, arguments)],
                            capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert result.returncode == expected, result.stderr + result.stdout
    return json.loads(result.stdout)


def test_cli_create_patch_run_status_and_failure(tmp_path):
    workspace = tmp_path / "工作区"
    file = tmp_path / "workflow.json"
    fields = {"language": {"value": "python"}, "value": {"value": "hello", "type": "str"},
              "code": {"value": "def main(value): return value.upper()"}, "output": {"value": "", "is_output": True}}
    definition = {"nodes": [{"id": "node", "type": "ProgrammingFunction", "category": "tools", "data": {
        "task_name": "tools.programming_function", "template": fields}}], "edges": []}
    file.write_text(json.dumps(definition), encoding="utf-8")
    created = command(workspace, "workflow", "create", "--file", file, "--title", "CLI test")
    assert not list(workspace.glob("*.zip"))
    wid = created["wid"]
    patch = tmp_path / "inputs.json"
    patch.write_text(json.dumps([{"node_id": "node", "field_name": "value", "value": "updated"}]), encoding="utf-8")
    updated = command(workspace, "workflow", "patch", wid, "--inputs", patch, "--expected-version", "1")
    assert updated["version"] == 2
    stale = command(workspace, "workflow", "patch", wid, "--inputs", patch, "--expected-version", "1", expected=2)
    assert "version changed" in stale["message"]
    result = command(workspace, "workflow", "run", wid)
    assert result["status"] == "FINISHED" and result["outputs"]["node"]["output"] == "UPDATED"
    status = command(workspace, "workflow", "status", result["rid"])
    assert status["workflow_version"] == 2
    patch.write_text(json.dumps([{"node_id": "node", "field_name": "code", "value": "def main(value): raise ValueError('sample')"}]), encoding="utf-8")
    failure = command(workspace, "workflow", "run", wid, "--inputs", patch, expected=1)
    assert failure["status"] == "FAILED"
    saved = command(workspace, "workflow", "get", wid)
    assert saved["data"]["nodes"][0]["data"]["template"]["code"]["value"] == "def main(value): return value.upper()"
    assert not list(workspace.glob("*.zip"))


@pytest.mark.parametrize("flag", ["--help", "--version"])
def test_help_does_not_initialize_workspace(tmp_path, flag):
    workspace = tmp_path / "unused"
    result = subprocess.run([sys.executable, str(CLI), "--workspace", str(workspace), flag], capture_output=True, timeout=10)
    assert result.returncode == 0 and not workspace.exists()


def test_external_settings_errors_do_not_print_or_store_credentials(tmp_path):
    settings = tmp_path / "settings.local.json"
    secret = "test-secret-that-must-not-appear"
    settings.write_text(json.dumps({"VERSION": "2", "endpoints": [{"api_key": secret}], "backends": {}}), encoding="utf-8")
    workspace = tmp_path / "private-workspace"
    result = command(workspace, "--settings", settings, "init", expected=2)
    assert secret not in json.dumps(result)
    database = workspace / "data/my_database.db"
    if database.exists():
        assert secret.encode() not in database.read_bytes()


def test_cli_upgrade_backs_up_before_settings_normalization_and_reuses_on_restart(tmp_path):
    from peewee import SqliteDatabase
    from peewee_migrate import Router

    workspace = tmp_path / "legacy"
    data = workspace / "custom-data"
    data.mkdir(parents=True)
    (workspace / "config.json").write_text('{"data_path": "custom-data"}', encoding="utf-8")
    database = SqliteDatabase(data / "my_database.db")
    original = json.dumps({"Bing": {"legacy": True}, "agent": {"auto_title": True}})
    try:
        Router(database, migrate_dir=CLI.parent / "migrations").run("005_add_workflow_version")
        database.execute_sql("CREATE TABLE message (id INTEGER PRIMARY KEY, text TEXT)")
        database.execute_sql("INSERT INTO message VALUES (1, 'original chat')")
        database.execute_sql(
            "INSERT INTO setting (data, create_time, update_time) VALUES (?, ?, ?)",
            (original, "2026-01-01", "2026-01-01"),
        )
    finally:
        database.close()
    (data / "attachment.txt").write_text("original attachment", encoding="utf-8")
    command(workspace, "init")
    backups = sorted(workspace.glob("*.zip"))
    assert backups
    preserved_original = False
    for index, path in enumerate(backups):
        with zipfile.ZipFile(path) as archive:
            assert archive.read("custom-data/attachment.txt") == b"original attachment"
            snapshot = tmp_path / f"snapshot-{index}.db"
            snapshot.write_bytes(archive.read("custom-data/my_database.db"))
        with sqlite3.connect(snapshot) as old:
            assert old.execute("SELECT * FROM message").fetchall() == [(1, "original chat")]
            if old.execute("SELECT data FROM setting").fetchone()[0] == original:
                preserved_original = True
    assert preserved_original, "The pre-import ZIP must preserve settings before normalization"
    with sqlite3.connect(data / "my_database.db") as current:
        assert not current.execute("SELECT name FROM sqlite_master WHERE name='message'").fetchall()
        assert current.execute("SELECT name FROM migratehistory WHERE name='006_remove_conversation_agent'").fetchone()
    command(workspace, "init")
    assert sorted(workspace.glob("*.zip")) == backups
