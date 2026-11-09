"""Test-only loopback KB API host; all writable state lives below --root."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DeterministicEmbeddings:
    def get(self, value):
        if isinstance(value, list):
            return [self.get(text) for text in value]
        vector = [0.0] * 16
        for term in re.findall(r"\w+", value.casefold()):
            hashed = hashlib.sha256(term.encode()).digest()
            vector[hashed[0] % len(vector)] += 1.0
        norm = math.sqrt(sum(number * number for number in vector)) or 1
        return [number / norm for number in vector]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    os.chdir(root)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    from docx import Document
    from api import knowledge_base_api
    from knowledge_base import KnowledgeService

    sources = root / "sources"
    imported = sources / "Imported"
    nested = imported / "nested"
    nested.mkdir(parents=True)
    (imported / "notes.txt").write_text(
        "PUBLIC_ALPHA acquisition notes. Alpha project budget is 450 dollars. 招标预算四百五十元。",
        encoding="utf-8",
    )
    document = Document()
    document.add_heading("Nested telescope report", 0)
    document.add_paragraph("NESTEDCOBALT telescope calibration results. Cobalt optics passed all checks.")
    document.save(nested / "report.docx")
    (sources / "other.txt").write_text("PRIVATE_ORANGE confidential orange orchard plans.", encoding="utf-8")
    (sources / "single.txt").write_text("SINGLE_AMBER imported through the multiple-file picker.", encoding="utf-8")
    originals = {str(path): digest(path) for path in sources.rglob("*") if path.is_file()}
    opened = []
    service = KnowledgeService(
        root / "data/knowledge-base",
        embedder_factory=lambda _: DeterministicEmbeddings(),
        opener=lambda path: opened.append(str(path)),
    )
    knowledge_base_api.knowledge_service = lambda: service
    import knowledge_base
    knowledge_base.knowledge_service = lambda: service
    snapshot = {"knowledge_bases": [], "agent_profile": {"knowledge_base_ids": []}}
    task_workspace = root / "task-agent/workspaces/kb-fixture-task"
    task_workspace.mkdir(parents=True)
    task_service = SimpleNamespace(task_root=root / "task-agent", store=SimpleNamespace(
        get_task=lambda tid: {"config_snapshot": snapshot} if tid == "kb-fixture-task" else None))
    api = knowledge_base_api.KnowledgeBaseAPI()
    selection = {"file": str(sources / "single.txt")}
    calls = []
    token = os.environ["KB_BROWSER_FIXTURE_TOKEN"]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            if self.headers.get("X-Test-Token") != token:
                self.send_error(403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 65536:
                    raise ValueError("Invalid test request size")
                request = json.loads(self.rfile.read(length))
                action, payload = request["action"], request.get("payload", {})
                if action.startswith("knowledge_base__"):
                    method = action.removeprefix("knowledge_base__")
                    if method in ("import_files", "import_directory"):
                        paths = payload.get("paths", [payload.get("path")])
                        if not all(Path(path).resolve().is_relative_to(sources) for path in paths):
                            raise ValueError("Only synthetic source paths are allowed")
                    result = getattr(api, method)(payload)
                    calls.append({"action": method, "status": result["status"]})
                elif action == "fixture_task_mount":
                    selected = service.selected_bases([payload["kb_id"]])
                    snapshot["knowledge_bases"] = selected
                    snapshot["agent_profile"]["knowledge_base_ids"] = [payload["kb_id"]]
                    result = {"success": True}
                elif action in {"task_agent__files", "task_agent__preview_file"}:
                    from task_agent import files
                    if action.endswith("__files"):
                        data = files.list_files(task_service, payload["task_id"], payload.get("root_id"))
                    else:
                        data = files.preview_file(task_service, payload["task_id"], payload["path"])
                    result = {"status": 200, "data": data}
                elif action == "open_folder_dialog":
                    result = [str(imported)]
                elif action == "open_file_dialog":
                    result = [selection["file"]]
                elif action == "fixture_select":
                    if payload["name"] not in ("single", "other"):
                        raise ValueError("Unknown synthetic file")
                    selection["file"] = str(sources / f'{payload["name"]}.txt')
                    result = {"success": True}
                elif action == "fixture_status":
                    with service._lock:
                        client = service.vectors._client()
                        collections = client.get_collections().collections
                        result = {
                            "sources_preserved": all(Path(path).is_file() and digest(Path(path)) == expected
                                                     for path, expected in originals.items()),
                            "source_count": len(originals),
                            "opened": opened,
                            "calls": calls,
                            "vector_engine": type(service.vectors).__name__,
                            "collections": [{"name": item.name, "points": client.count(item.name).count}
                                            for item in collections],
                        }
                elif action == "fixture_shutdown":
                    result = {"success": True}
                    threading.Thread(target=server.shutdown, daemon=True).start()
                else:
                    raise ValueError("Unknown fixture action")
                content = json.dumps(result, ensure_ascii=False).encode()
                self.send_response(200)
            except Exception as error:
                content = json.dumps({"fixture_error": type(error).__name__, "message": str(error)}).encode()
                self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    print("KB_FIXTURE_READY=" + json.dumps({"port": server.server_port}), flush=True)
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()
        service.close()
        print("KB_FIXTURE_CLOSED", flush=True)


if __name__ == "__main__":
    main()
