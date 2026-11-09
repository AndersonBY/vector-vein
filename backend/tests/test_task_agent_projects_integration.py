import json
import os
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from task_agent_scenario import ScenarioModelHandler


class ProjectModel(ScenarioModelHandler):
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        users = [
            message["content"]
            for message in payload["messages"]
            if message["role"] == "user"
        ]
        tools = [
            message for message in payload["messages"] if message["role"] == "tool"
        ]
        goal = users[-1]
        call = None
        if "FOLLOWUP" not in goal:
            target = goal.split("SECONDARY=", 1)[1].splitlines()[0].strip()
            child = "create_sub_task" not in {
                tool["function"]["name"] for tool in payload.get("tools", [])
            }
            plans = (
                [
                    (
                        "write_file",
                        {
                            "path": str(Path(target) / "child.txt"),
                            "content": "child-result",
                        },
                    )
                ]
                if child
                else [
                    (
                        "write_file",
                        {"path": "primary.txt", "content": "primary-result"},
                    ),
                    (
                        "create_sub_task",
                        {
                            "agent_id": "worker",
                            "task_description": "Write one file. SECONDARY=" + target,
                            "wait_for_completion": True,
                        },
                    ),
                    (
                        "bash",
                        {
                            "command": "printf secondary-shell > shell.txt",
                            "exec_dir": target,
                            "yield_time_ms": 10000,
                        },
                    ),
                    ("read_file", {"path": str(Path(target) / "child.txt")}),
                ]
            )
            if len(tools) < len(plans):
                name, args = plans[len(tools)]
                call = {
                    "index": 0,
                    "id": f"project-{len(tools)}",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(args)},
                }
        delta = {
            "role": "assistant",
            "content": "Working" if call else "Project completed",
        }
        if call:
            delta["tool_calls"] = [call]
        chunks = [
            self._chunk(payload, delta),
            self._chunk(payload, {}, "tool_calls" if call else "stop"),
        ]
        body = (
            "".join("data: " + json.dumps(chunk) + "\n\n" for chunk in chunks)
            + "data: [DONE]\n\n"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_project_native_server_primary_additional_child_approval_and_restart(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), ProjectModel)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in {"VECTORVEIN_LLM_SETTINGS_FILE", "VECTORVEIN_OUTPUT_DIR"}
        }
        result = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                str(Path(__file__).with_name("task_agent_projects_smoke.py")),
                str(tmp_path),
                str(server.server_port),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=150,
            env=env,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout) == {
            "completed": True,
            "child_secondary": True,
            "shell_secondary": True,
            "restart": True,
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
