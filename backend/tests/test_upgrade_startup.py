"""Exercise startup entrypoints in disposable workspaces without starting a GUI."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("entrypoint", ["cli", "desktop", "fake"])
def test_upgrade_startup_preflight_and_failure(tmp_path, entrypoint):
    script = r'''
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, sys.argv[1])
import cli
import models
import models.base as base
from utilities.config import config, cache
from utilities.upgrade_backup import UpgradeBackupError
import utilities.upgrade_backup as backup
import peewee_migrate

events = []
def preflight(database, **kwargs):
    assert database is models.database
    events.append("backup")
    raise UpgradeBackupError("Safe backup failure: check space and permissions")

router = Mock(side_effect=lambda *a, **kw: events.append("router"))
try:
    with patch.object(backup, "ensure_v1_upgrade_backup", preflight), \
         patch.object(peewee_migrate, "Router", router), \
         patch.object(models, "create_tables") as create:
        if sys.argv[2] == "cli":
            try:
                cli.initialize()
                raise AssertionError("initialize continued")
            except UpgradeBackupError:
                pass
            assert events == ["backup"]
            create.assert_not_called()
            with patch.object(cli, "execute") as execute:
                assert cli.main(["--workspace", str(Path.cwd()), "init"]) == 2
                execute.assert_not_called()
        elif sys.argv[2] == "fake":
            fake_router = Mock()
            router.side_effect = None
            router.return_value = fake_router
            base.run_migrations(fake=True)
            assert events == []
            fake_router.run.assert_called_once_with(fake=True)
        else:
            # Stub optional desktop dependencies; execute the actual MainServer
            # constructor and entrypoint without native windows or services.
            names = [
                "webview", "webview.dom", "webview.window", "celery_worker",
                "workflow_stream.server", "fastapi_server", "tts_server.server",
                "utilities.file_processing", "utilities.general",
                "utilities.network", "utilities.shortcuts", "utilities.workflow",
                "utilities.workflow_recovery",
            ]
            stubs = {name: Mock() for name in names}
            stubs["webview.window"].Window = object
            with patch.dict(sys.modules, stubs):
                import main
                assert main.main() == 1
                assert events == ["backup"]
                create.assert_not_called()
                router.assert_not_called()
                stubs["utilities.file_processing"].static_file_server.start.assert_not_called()
                stubs["celery_worker"].CeleryWorkerManager.assert_not_called()
                stubs["utilities.workflow"].workflow_scheduler.start.assert_not_called()
                stubs["utilities.workflow_recovery"].recover_interrupted_runs.assert_not_called()
                stubs["webview"].create_window.assert_called_once()
                html = stubs["webview"].create_window.call_args.kwargs["html"]
                assert "旧数据未迁移" in html and "Safe backup failure" in html
                stubs["webview"].start.assert_called_once()
finally:
    cache.close()
    models.database.close()
    config.close()
'''
    environment = {key: value for key, value in os.environ.items()
                   if key not in ("VECTORVEIN_LLM_SETTINGS_FILE", "VECTORVEIN_OUTPUT_DIR")}
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", script,
         str(Path(__file__).resolve().parents[1]), entrypoint],
        cwd=tmp_path, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    if entrypoint == "cli":
        payload = json.loads(result.stdout[result.stdout.index("{"):])
        assert payload == {"error": "UpgradeBackupError", "message": "Safe backup failure: check space and permissions"}


@pytest.mark.parametrize("entrypoint", ["config", "initialize", "cli", "desktop-import", "desktop-launch"])
def test_early_backup_failure_precedes_config_cache_models_and_services(tmp_path, entrypoint):
    script = r'''
import json
from pathlib import Path
import runpy
import sqlite3
import sys
from unittest.mock import Mock, patch

sys.path.insert(0, sys.argv[1])
import utilities.upgrade_backup as backup
root = Path.cwd()
data = root / "custom-data"
data.mkdir()
database = data / "my_database.db"
with sqlite3.connect(database) as connection:
    connection.execute("CREATE TABLE message (id INTEGER PRIMARY KEY, text TEXT)")
    connection.execute("INSERT INTO message VALUES (1, 'original chat')")
before = database.read_bytes()
config = root / "config.json"
config.write_text('{"data_path": "custom-data", "theme": "original"}', encoding="utf-8")
original_config = config.read_bytes()

def fail(*args, **kwargs):
    raise OSError("injected failure")

stubs = {name: Mock() for name in ("webview", "webview.dom", "webview.window")}
with patch.object(backup, "_create", fail), patch.dict(sys.modules, stubs):
    name = sys.argv[2]
    if name in ("config", "initialize", "desktop-import"):
        try:
            if name == "config":
                import utilities.config
            elif name == "initialize":
                import cli
                cli.initialize()
            else:
                import main
            raise AssertionError("early backup failure did not propagate")
        except backup.UpgradeBackupError:
            pass
    elif name == "cli":
        import cli
        assert cli.main(["--workspace", str(root), "init"]) == 2
    else:
        try:
            runpy.run_path(str(Path(sys.argv[1]) / "main.py"), run_name="__main__")
            raise AssertionError("launcher did not exit")
        except SystemExit as exc:
            assert exc.code == 1
        stubs["webview"].create_window.assert_called_once()
        assert "旧数据未迁移" in stubs["webview"].create_window.call_args.kwargs["html"]
        stubs["webview"].start.assert_called_once()
    assert "utilities.config.config" not in sys.modules
    assert "utilities.config.cache" not in sys.modules
    assert "utilities.config.settings" not in sys.modules
    assert "models" not in sys.modules
    assert "celery_worker" not in sys.modules
    assert database.read_bytes() == before
    assert config.read_bytes() == original_config
    assert not (data / "cache").exists()
'''
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", script,
         str(Path(__file__).resolve().parents[1]), entrypoint],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stderr + result.stdout
