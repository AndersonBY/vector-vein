import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class ErrorEndpoint(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        status = int(self.path.split("/")[1])
        body = json.dumps({"error":{"message":"SECRET_PROVIDER_BODY local-test-credential", "code":"model_not_found" if status == 404 else "invalid_request_error", "param":"reasoning_effort" if status == 422 else None}}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def test_actual_http_failures_survive_app_server_projection_and_restart(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1",0), ErrorEndpoint)
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    env = {key:value for key,value in os.environ.items() if key not in {"VECTORVEIN_LLM_SETTINGS_FILE","VECTORVEIN_OUTPUT_DIR"}}
    try:
        result = subprocess.run([sys.executable,"-X","utf8",str(Path(__file__).with_name("task_agent_error_smoke.py")),str(tmp_path),str(server.server_port)],
                                env=env,capture_output=True,text=True,encoding="utf-8",timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout) == {"passed":True,"cases":4,"restored":True}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
