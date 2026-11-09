"""Packaging checks that do not run PyInstaller or open a desktop window."""
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

import build
from task_agent_package_smoke import smoke


def test_production_archive_does_not_include_migration_bytecode(tmp_path, monkeypatch):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_init.py").write_text("# migration", encoding="utf-8")
    (migrations / "__pycache__").mkdir()
    (migrations / "__pycache__/001_init.cpython-312.pyc").write_bytes(b"bytecode")
    (migrations / "stale.pyc").write_bytes(b"bytecode")
    dist = tmp_path / "dist"
    monkeypatch.setattr(build, "MIGRATIONS_DIR", migrations)
    monkeypatch.setattr(build, "DIST_DIR", dist)
    monkeypatch.setattr(build, "APP_DIST_DIR", dist / "vector-vein")
    monkeypatch.setattr(build, "run_cmd", lambda *_args: None)
    build.build_production("1.0.0")
    with zipfile.ZipFile(next(dist.glob("*.zip"))) as archive:
        names = archive.namelist()
        assert "vector-vein/migrations/001_init.py" in names
        assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)
        assert archive.read("vector-vein/version.txt") == b"1.0.0"


@pytest.fixture
def package(tmp_path):
    root = tmp_path / "package"
    root.mkdir()
    cli = root / "VectorVeinCLI"
    cli.touch()
    (root / "version.txt").write_text("1.0.0", encoding="utf-8")
    for name in (
        "web/index.html", "web/favicon.ico", "web/logo.svg", "web/assets/chunk.js",
        "assets/tiktoken_cache/token", "pymupdf/layout/resources/onnx/model.onnx",
    ):
        path = root / "_internal" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    (root / "migrations").mkdir()
    (root / "migrations/001_init.py").touch()
    return cli


def test_smoke_runs_frozen_cli_in_isolated_workspace(package, monkeypatch):
    calls = []

    def run(command, **kwargs):
        workspace = Path(command[2])
        assert kwargs["cwd"] == workspace
        assert workspace != package.parent
        assert kwargs["timeout"] == 120
        assert kwargs["check"]
        assert "PYTHONPATH" not in kwargs["env"]
        calls.append(command[3:])
        output = ""
        if command[-1] == "--version":
            output = "1.0.0\n"
        if command[-1] == "serve":
            request = json.loads(kwargs["input"])
            assert request["params"]["clientInfo"]["name"] == "桌面验收"
            database = workspace / "data/task-agent/sessions.db"
            database.parent.mkdir(parents=True)
            database.touch()
            output = '{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"v5"}}\n'
        return subprocess.CompletedProcess(command, 0, stdout=output)

    monkeypatch.setenv("PYTHONPATH", "source-tree")
    monkeypatch.setattr(subprocess, "run", run)
    smoke(package, "1.0.0")
    assert calls == [["--help"], ["--version"], ["init"], ["task-agent", "serve"]]


def test_smoke_rejects_bundled_local_config_before_execution(package, monkeypatch):
    (package.parent / "_internal/config.json").write_text("{}", encoding="utf-8")
    with pytest.raises(AssertionError, match="config.json"):
        smoke(package, "1.0.0")


def test_smoke_rejects_missing_pdf_model_resources(package):
    (package.parent / "_internal/pymupdf/layout/resources/onnx/model.onnx").unlink()
    with pytest.raises(AssertionError, match="PyMuPDF"):
        smoke(package, "1.0.0")
