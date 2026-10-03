from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


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


def test_help_does_not_initialize_workspace(tmp_path):
    workspace = tmp_path / "unused"
    result = subprocess.run([sys.executable, str(CLI), "--workspace", str(workspace), "--help"], capture_output=True, timeout=10)
    assert result.returncode == 0 and not workspace.exists()


def test_external_settings_errors_do_not_print_or_store_credentials(tmp_path):
    settings = tmp_path / "settings.local.json"
    secret = "test-secret-that-must-not-appear"
    settings.write_text(json.dumps({"VERSION": "2", "endpoints": [{"api_key": secret}], "backends": {}}), encoding="utf-8")
    workspace = tmp_path / "private-workspace"
    result = command(workspace, "--settings", settings, "init", expected=2)
    assert secret not in json.dumps(result)
    assert secret.encode() not in (workspace / "data/my_database.db").read_bytes()
