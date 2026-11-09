import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class WorkflowModel(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        called = any(message.get("role") == "tool" for message in body["messages"])
        delta = {"role": "assistant", "content": "Workflow result received." if called else "Running the selected workflow."}
        if not called:
            tool = next(item["function"]["name"] for item in body["tools"] if item["function"]["name"].startswith("workflow_"))
            delta["tool_calls"] = [{"index": 0, "id": "workflow-call", "type": "function", "function": {"name": tool, "arguments": json.dumps({"text": "Synthetic workflow report"})}}]
        chunks = [{"id": "mock", "object": "chat.completion.chunk", "created": 1, "model": body["model"], "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                  {"id": "mock", "object": "chat.completion.chunk", "created": 1, "model": body["model"], "choices": [{"index": 0, "delta": {}, "finish_reason": "stop" if called else "tool_calls"}], "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}}]
        encoded = ("".join("data: " + json.dumps(chunk) + "\n\n" for chunk in chunks) + "data: [DONE]\n\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *args):
        pass


def test_app_server_workflow_approval_feedback_recovery_denial_and_cancel(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), WorkflowModel)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    env = {key: value for key, value in os.environ.items() if key not in {"VECTORVEIN_LLM_SETTINGS_FILE", "VECTORVEIN_OUTPUT_DIR"}}
    try:
        result = subprocess.run([sys.executable, "-X", "utf8", str(Path(__file__).with_name("task_agent_workflow_appserver_smoke.py")), str(server.server_port)],
                                cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8", timeout=150)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads((tmp_path / "workflow-bridge-report.json").read_text(encoding="utf-8")) == {"passed": True, "runs": 2}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
