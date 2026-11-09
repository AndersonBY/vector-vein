import json
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from task_agent_scenario import ScenarioModelHandler


def test_real_tools_question_restart_reply_file_and_replay(tmp_path):
    ScenarioModelHandler.calls = []
    ScenarioModelHandler.delay = 0.3
    server = ThreadingHTTPServer(("127.0.0.1", 0), ScenarioModelHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        script = Path(__file__).with_name("task_agent_interactive_smoke.py")
        result = subprocess.run([sys.executable, "-X", "utf8", str(script), str(tmp_path), str(server.server_port)],
                                capture_output=True, text=True, encoding="utf-8", timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout)["status"] == "COMPLETED"
        assert len(ScenarioModelHandler.calls) == 7
        assert any("write_file" in json.dumps(call.get("tools")) for call in ScenarioModelHandler.calls)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
