from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from typing import Any


class DeterministicMCPAppServerModelHandler(BaseHTTPRequestHandler):
    requests: list[dict[str, Any]] = []

    def _send_sse(self, model: str, delta: dict[str, Any], finish_reason: str) -> None:
        chunks = [
            {
                "id": "mock-mcp-1",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
            },
            {
                "id": "mock-mcp-1",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
                "usage": {"prompt_tokens": 25, "completion_tokens": 12, "total_tokens": 37},
            },
        ]
        encoded = ("".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        self.__class__.requests.append(payload)

        model = payload.get("model", "")
        messages = payload.get("messages") or []
        tools = payload.get("tools") or []
        tool_names = [t["function"]["name"] for t in tools if isinstance(t, dict) and "function" in t]

        # 1. Risk reviewer calls (tool-free)
        if model == "mock-reviewer-allow":
            assert tools == []
            user_ev = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "{}")
            ev_obj = json.loads(user_ev)
            assert ev_obj.get("mcp_tool") is not None
            assert ev_obj["mcp_tool"].get("untrusted_server_metadata") is True
            assert "SYNTHETIC_MCP_APP_SECRET_987654" not in user_ev
            verdict = json.dumps({"decision": "allow", "risk": "low", "reason": "within_scope"})
            self._send_sse(model, {"role": "assistant", "content": verdict}, "stop")
            return

        if model == "mock-reviewer-fail":
            assert tools == []
            self._send_sse(model, {"role": "assistant", "content": "not valid json"}, "stop")
            return

        # 2. Primary / child agent calls: verify tool scope and open JSON Schema preservation!
        step_tool = next((n for n in tool_names if "stateful_step" in n), None)
        media_tool = next((n for n in tool_names if "media_and_error" in n), None)
        assert step_tool is not None, f"stateful_step missing from {tool_names}"
        assert media_tool is not None, f"media_and_error missing from {tool_names}"
        # Unselected peer_info tool on the same server MUST NOT be exposed!
        assert not any("peer_info" in n for n in tool_names), f"Unselected peer_info leaked into {tool_names}"
        # Disabled shell and write_file MUST NOT be exposed!
        assert "bash" not in tool_names
        assert "write_file" not in tool_names

        # Check final model-facing JSON Schema on media_and_error preserves open object + $ref parameter
        media_schema = next(t["function"]["parameters"] for t in tools if t["function"]["name"] == media_tool)
        assert media_schema.get("additionalProperties") is not False
        props = media_schema.get("properties") or {}
        assert "$ref" in props
        assert props.get("open_meta", {}).get("additionalProperties") is not False

        user_texts = [str(m.get("content") or "") for m in messages if m.get("role") == "user"]
        last_user = user_texts[-1] if user_texts else ""
        all_user = "\n".join(user_texts)
        tool_msgs = [m for m in messages if m.get("role") == "tool"]

        # Child sub-agent execution
        if "CHILD_CALL_STEP" in all_user:
            assert "create_sub_task" not in tool_names
            if not tool_msgs:
                self._send_sse(
                    model,
                    {
                        "role": "assistant",
                        "content": "Child calling stateful_step.",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "child-tc-1",
                                "type": "function",
                                "function": {
                                    "name": step_tool,
                                    "arguments": json.dumps({"tag": "child_step"}),
                                },
                            }
                        ],
                    },
                    "tool_calls",
                )
            else:
                self._send_sse(
                    model,
                    {"role": "assistant", "content": f"CHILD_DONE:{tool_msgs[-1].get('content', '')}"},
                    "stop",
                )
            return

        # Scenario: follow-up turn on task_ask_allow ("SCENARIO:SINGLE_STEP tag=after_endpoint_change")
        if "SCENARIO:SINGLE_STEP" in last_user:
            tag_val = last_user.split("tag=", 1)[1].strip().split()[0]
            # Count only tool messages after the last user message
            last_user_idx = max(i for i, m in enumerate(messages) if m.get("role") == "user")
            turn_tool_msgs = [m for m in messages[last_user_idx + 1 :] if m.get("role") == "tool"]
            if not turn_tool_msgs:
                self._send_sse(
                    model,
                    {
                        "role": "assistant",
                        "content": f"Calling stateful_step with {tag_val}.",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": f"call-{tag_val[:12]}",
                                "type": "function",
                                "function": {
                                    "name": step_tool,
                                    "arguments": json.dumps({"tag": tag_val}),
                                },
                            }
                        ],
                    },
                    "tool_calls",
                )
            else:
                self._send_sse(
                    model,
                    {"role": "assistant", "content": f"SINGLE_STEP_DONE:{turn_tool_msgs[-1].get('content', '')}"},
                    "stop",
                )
            return

        if "SCENARIO:TWO_STEPS_AND_CHILD" in all_user:
            if len(tool_msgs) == 0:
                self._send_sse(
                    model,
                    {
                        "role": "assistant",
                        "content": "Step 1.",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "parent-step-1",
                                "type": "function",
                                "function": {
                                    "name": step_tool,
                                    "arguments": json.dumps({"tag": "step_one"}),
                                },
                            }
                        ],
                    },
                    "tool_calls",
                )
            elif len(tool_msgs) == 1:
                self._send_sse(
                    model,
                    {
                        "role": "assistant",
                        "content": "Step 2.",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "parent-step-2",
                                "type": "function",
                                "function": {
                                    "name": step_tool,
                                    "arguments": json.dumps({"tag": "step_two"}),
                                },
                            }
                        ],
                    },
                    "tool_calls",
                )
            elif len(tool_msgs) == 2:
                self._send_sse(
                    model,
                    {
                        "role": "assistant",
                        "content": "Delegating to worker.",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "parent-sub-1",
                                "type": "function",
                                "function": {
                                    "name": "create_sub_task",
                                    "arguments": json.dumps(
                                        {
                                            "agent_id": "worker",
                                            "task_description": "CHILD_CALL_STEP",
                                            "wait_for_completion": True,
                                        }
                                    ),
                                },
                            }
                        ],
                    },
                    "tool_calls",
                )
            else:
                self._send_sse(
                    model,
                    {"role": "assistant", "content": "TWO_STEPS_AND_CHILD_COMPLETE"},
                    "stop",
                )
            return

        if "SCENARIO:MEDIA_AND_TOOL_ERROR" in all_user:
            if len(tool_msgs) == 0:
                self._send_sse(
                    model,
                    {
                        "role": "assistant",
                        "content": "Calling media_and_error (success image).",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "media-ok",
                                "type": "function",
                                "function": {
                                    "name": media_tool,
                                    "arguments": json.dumps(
                                        {
                                            "fail": False,
                                            "open_meta": {"nested_arbitrary_key": "allowed"},
                                            "$ref": "legitimate-ref-param",
                                        }
                                    ),
                                },
                            }
                        ],
                    },
                    "tool_calls",
                )
            elif len(tool_msgs) == 1:
                self._send_sse(
                    model,
                    {
                        "role": "assistant",
                        "content": "Calling media_and_error (tool error).",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "media-err",
                                "type": "function",
                                "function": {
                                    "name": media_tool,
                                    "arguments": json.dumps({"fail": True}),
                                },
                            }
                        ],
                    },
                    "tool_calls",
                )
            else:
                self._send_sse(
                    model,
                    {"role": "assistant", "content": "MEDIA_AND_ERROR_COMPLETE"},
                    "stop",
                )
            return

        if "SCENARIO:SLOW_TIMEOUT" in all_user:
            if not tool_msgs:
                self._send_sse(
                    model,
                    {
                        "role": "assistant",
                        "content": "Calling slow stateful_step.",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "slow-to-1",
                                "type": "function",
                                "function": {
                                    "name": step_tool,
                                    "arguments": json.dumps({"tag": "timeout_call", "delay": 5.0}),
                                },
                            }
                        ],
                    },
                    "tool_calls",
                )
            else:
                # Model observes tool_outcome_unknown and finishes without re-calling
                self._send_sse(
                    model,
                    {"role": "assistant", "content": f"OBSERVED_UNKNOWN:{tool_msgs[-1].get('content', '')}"},
                    "stop",
                )
            return

        if "SCENARIO:SLOW_INFLIGHT" in all_user:
            if not tool_msgs:
                self._send_sse(
                    model,
                    {
                        "role": "assistant",
                        "content": "Calling slow inflight stateful_step.",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "slow-inf-1",
                                "type": "function",
                                "function": {
                                    "name": step_tool,
                                    "arguments": json.dumps({"tag": "inflight_call", "delay": 4.0}),
                                },
                            }
                        ],
                    },
                    "tool_calls",
                )
            else:
                self._send_sse(
                    model,
                    {"role": "assistant", "content": f"RECOVERED_INFLIGHT:{tool_msgs[-1].get('content', '')}"},
                    "stop",
                )
            return

        self._send_sse(model, {"role": "assistant", "content": "Fallback completion."}, "stop")

    def log_message(self, *args: Any) -> None:
        pass


def test_real_appserver_mcp_end_to_end_approvals_stateful_sessions_media_recovery_and_deletion(tmp_path: Path) -> None:
    DeterministicMCPAppServerModelHandler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), DeterministicMCPAppServerModelHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    script = Path(__file__).with_name("task_agent_mcp_appserver_smoke.py")
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"VECTORVEIN_LLM_SETTINGS_FILE", "VECTORVEIN_OUTPUT_DIR"}
    }
    try:
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(script), str(tmp_path), str(server.server_port)],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=240,
        )
        assert result.returncode == 0, result.stderr + "\n" + result.stdout
        assert json.loads(result.stdout.strip().splitlines()[-1]) == {"passed": True}
        # Verify no synthetic secret or base64 image was ever sent to the model or reviewer
        serialized_requests = json.dumps(DeterministicMCPAppServerModelHandler.requests)
        assert "SYNTHETIC_MCP_APP_SECRET_987654" not in serialized_requests
        assert "iVBORw0KGgo" not in serialized_requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
