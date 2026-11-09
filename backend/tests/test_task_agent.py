from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class MockModelHandler(BaseHTTPRequestHandler):
    requests = []

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).requests.append(payload)
        content = "模拟交付：目标已处理。"
        if payload.get("stream"):
            chunks = [
                {"id": "mock", "object": "chat.completion.chunk", "created": 1, "model": payload["model"],
                 "choices": [{"index": 0, "delta": {"role": "assistant", "content": content}, "finish_reason": None}]},
                {"id": "mock", "object": "chat.completion.chunk", "created": 1, "model": payload["model"],
                 "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                 "usage": {"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28}},
            ]
            body = "".join(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        else:
            result = {
                "id": "mock", "object": "chat.completion", "created": 1, "model": payload["model"],
                "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28},
            }
            body = json.dumps(result, ensure_ascii=False)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
        encoded = body.encode("utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *args):
        pass


def test_task_agent_server_creates_empty_session_store(tmp_path):
    cli = Path(__file__).resolve().parents[1] / "cli.py"
    message = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"clientInfo": {"name": "空工作区验收"}, "capabilities": {"experimentalApi": False, "optOutNotificationMethods": []}},
    })
    result = subprocess.run(
        [sys.executable, str(cli), "--workspace", str(tmp_path), "task-agent", "serve"],
        input=message + "\n", capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert json.loads(result.stdout)["result"]["protocolVersion"] == "v5"
    assert (tmp_path / "data" / "task-agent" / "sessions.db").is_file()


def test_scheduled_agent_uses_real_app_server_project_continuation_and_completion_options(tmp_path):
    MockModelHandler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockModelHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        script = Path(__file__).with_name("task_agent_schedule_smoke.py")
        result = subprocess.run([sys.executable, "-X", "utf8", str(script), str(tmp_path), str(server.server_port)],
            capture_output=True, text=True, encoding="utf-8", timeout=180)
        assert result.returncode == 0, result.stderr + result.stdout
        assert json.loads(result.stdout) == {"status": "COMPLETED", "tasks": 2, "notifications": 1, "model_calls": 4}
        assert len(MockModelHandler.requests) == 4
        assert [request["reasoning_effort"] for request in MockModelHandler.requests] == ["max", "low", "low", "low"]
        assert len(MockModelHandler.requests[1]["messages"]) > len(MockModelHandler.requests[0]["messages"])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_task_agent_full_flow_restarts_and_preserves_business_history(tmp_path):
    MockModelHandler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockModelHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    script = Path(__file__).with_name("task_agent_flow_smoke.py")
    try:
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(script), str(tmp_path), str(server.server_port)],
            capture_output=True, text=True, encoding="utf-8", timeout=180,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        assert json.loads(result.stdout) == {"status": "COMPLETED", "messages": 4}
        assert len(MockModelHandler.requests) == 2
        assert all(request["reasoning_effort"] == "max" for request in MockModelHandler.requests)
        assert (tmp_path / "data" / "task-agent" / "sessions.db").is_file()
        assert (tmp_path / "data" / "task-agent" / "tasks.db").is_file()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
