import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class RuntimeModelHandler(BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).calls.append({"path": self.path, "payload": payload})
        number = len(type(self).calls)
        if number == 1:
            message = {"role": "assistant", "content": None, "tool_calls": [{"id": "question_call", "type": "function", "function": {"name": "ask_user", "arguments": json.dumps({"question": "Continue to the approval check?"})}}]}
        elif number == 2:
            message = {"role": "assistant", "content": None, "tool_calls": [{"id": "bash_call", "type": "function", "function": {"name": "bash", "arguments": json.dumps({"command": "echo MUST_NOT_EXECUTE"})}}]}
        else:
            message = {"role": "assistant", "content": "A concise verified update and retained summary of the task. " * 40}
        if not payload.get("tools"):
            message = {"role": "assistant", "content": json.dumps({"summary_version": "2.0",
                "original_user_messages": ["Ask a question, then verify the next operation requires approval."],
                "user_constraints": ["Do not execute the denied command."], "decisions": ["The command was denied."],
                "progress": ["Model and permission settings were changed and preserved after restart."],
                "files_examined_or_modified": [], "errors_and_fixes": [], "remaining_tasks": [], "current_state": "Verified."})}
        usage = {"prompt_tokens": 1000, "completion_tokens": 10, "total_tokens": 1010, "prompt_tokens_details": {"cached_tokens": 600}}
        result = {"id": f"runtime_{number}", "object": "chat.completion", "created": 1, "model": payload["model"], "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls" if message.get("tool_calls") else "stop"}], "usage": usage}
        if payload.get("stream"):
            chunk = {**result, "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": message, "finish_reason": result["choices"][0]["finish_reason"]}]}
            content = f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n"
            content_type = "text/event-stream"
        else:
            content, content_type = json.dumps(result), "application/json"
        body = content.encode()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def test_actual_appserver_runtime_model_policy_and_context(tmp_path):
    RuntimeModelHandler.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), RuntimeModelHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        environment = {key: value for key, value in os.environ.items() if key not in {"VECTORVEIN_LLM_SETTINGS_FILE", "VECTORVEIN_OUTPUT_DIR"}}
        result = subprocess.run([sys.executable, "-X", "utf8", str(Path(__file__).with_name("task_agent_runtime_settings_smoke.py")), str(tmp_path), str(server.server_port)],
            capture_output=True, text=True, encoding="utf-8", env=environment, timeout=240)
        assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-6000:]
        report = json.loads(result.stdout)
        assert report["passed"] is True
        assert report["native_compaction"] == "completed"
        assert RuntimeModelHandler.calls[0]["path"] == "/one/v1/chat/completions"
        primary = [call for call in RuntimeModelHandler.calls if call["payload"].get("tools")]
        summaries = [call for call in RuntimeModelHandler.calls if not call["payload"].get("tools")]
        assert len(primary) >= 10 and summaries
        assert all(call["path"] == "/two/v1/chat/completions" for call in primary[1:])
        # Native selections change primary calls; the independent summary route stays pinned.
        assert all(call["path"] == "/one/v1/chat/completions" for call in summaries)
        assert RuntimeModelHandler.calls[0]["payload"].get("reasoning_effort") == "high"
        assert all(call["payload"].get("reasoning_effort") == "low" for call in primary[1:])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
