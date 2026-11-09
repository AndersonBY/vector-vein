"""Exercise the frozen CLI outside the source tree, without opening a GUI."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def smoke(cli: Path, version: str):
    cli = cli.resolve(strict=True)
    assert (cli.parent / "version.txt").read_text(encoding="utf-8").strip() == version
    resources = cli.parent / "_internal"
    for relative in ("web/index.html", "web/favicon.ico", "web/logo.svg", "web/assets", "assets/tiktoken_cache"):
        assert (resources / relative).exists(), relative
    assert list((resources / "pymupdf/layout").rglob("*.onnx")), "PyMuPDF layout model resources"
    migrations = cli.parent / "migrations"
    assert list(migrations.glob("*.py"))
    assert not list(migrations.rglob("*.pyc"))
    for name in ("data", "config.json", ".env", "tests", ".pytest_cache"):
        assert not (cli.parent / name).exists(), name
        assert not (resources / name).exists(), name

    with tempfile.TemporaryDirectory(prefix="vectorvein-package-smoke-") as temporary:
        workspace = Path(temporary)
        env = {key: value for key, value in os.environ.items() if key not in ("PYTHONPATH", "PYTHONHOME")}
        env["PYTHONIOENCODING"] = "utf-8"

        def run(*args, input=None):
            return subprocess.run(
                [str(cli), "--workspace", str(workspace), *args],
                input=input, capture_output=True, encoding="utf-8", errors="strict",
                cwd=workspace, env=env, timeout=120, check=True,
            ).stdout

        run("--help")
        assert run("--version").strip() == version
        run("init")
        request = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "clientInfo": {"name": "桌面验收"},
                "capabilities": {"experimentalApi": False, "optOutNotificationMethods": []},
            },
        }
        output = run("task-agent", "serve", input=json.dumps(request, ensure_ascii=False) + "\n")
        responses = [json.loads(line) for line in output.splitlines() if line.strip()]
        response = next(item for item in responses if item.get("id") == 1)
        assert response["result"]["protocolVersion"] == "v5"
        assert (workspace / "data/task-agent/sessions.db").is_file()


if __name__ == "__main__":
    smoke(Path(sys.argv[1]), sys.argv[2])
