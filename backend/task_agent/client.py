"""Own one vv-agent App Server child process and its JSON-RPC transport."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from collections import deque
from pathlib import Path


class TaskAgentError(RuntimeError):
    def __init__(self, message: str, *, code: int | None = None, data=None):
        super().__init__(message)
        self.code = code
        self.data = data


def app_server_command(workspace: Path) -> list[str]:
    if getattr(sys, "frozen", False):
        name = "VectorVeinCLI.exe" if os.name == "nt" else "VectorVeinCLI"
        executable = Path(sys.executable).resolve().with_name(name)
        return [str(executable), "--workspace", str(workspace), "task-agent", "serve"]
    cli = Path(__file__).resolve().parents[1] / "cli.py"
    return [sys.executable, "-X", "utf8", str(cli), "--workspace", str(workspace), "task-agent", "serve"]


class AppServerProcess:
    def __init__(self, workspace: Path, *, timeout: float = 30, command: list[str] | None = None):
        self.workspace = workspace.resolve()
        self.timeout = timeout
        self.command = command or app_server_command(self.workspace)
        self.process: subprocess.Popen[str] | None = None
        self._protocol_version = ""
        self._next_request_id = 0
        self._pending: dict[int, queue.Queue[dict]] = {}
        self._pending_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._reader_active = False
        self._stderr_lines = deque(maxlen=50)
        self._live_lock = threading.Lock()
        self._live = {}
        self._failures = {}

    @property
    def stderr_diagnostics(self) -> list[str]:
        return list(self._stderr_lines)

    def live_text(self, thread_id: str):
        with self._live_lock:
            value = self._live.get(thread_id)
            return dict(value) if value else None

    def execution_failed(self, thread_id, turn_id):
        with self._live_lock:
            return self._failures.get(thread_id) == turn_id

    def clear_execution_failure(self, thread_id):
        with self._live_lock:
            self._failures.pop(thread_id, None)

    def forget_tasks(self, thread_ids):
        with self._live_lock:
            for thread_id in thread_ids:
                self._live.pop(thread_id, None)
                self._failures.pop(thread_id, None)

    def _observe(self, message):
        params = message.get("params", {})
        tid = params.get("threadId")
        if not tid:
            return
        with self._live_lock:
            if message["method"] == "turn/completed" and params.get("error") and params.get("status") == "failed":
                self._failures[tid] = params.get("turnId")
            elif message["method"] == "item/started" and params.get("type") == "modelCall":
                self._failures.pop(tid, None)
            if message["method"] == "item/agentMessage/delta":
                turn = params.get("turnId")
                previous = self._live.get(tid, {})
                text = previous.get("text", "") if previous.get("turn_id") == turn else ""
                self._live[tid] = {"turn_id": turn, "text": (text + params.get("delta", ""))[-65536:]}
            elif message["method"] == "turn/completed" or (message["method"] == "item/completed" and params.get("type") in {"agentMessage", "modelCall"}):
                self._live.pop(tid, None)

    def start(self) -> dict:
        with self._lifecycle_lock:
            if self.process is not None and self.process.poll() is None and self._reader_active:
                return self.status()
            self._stop()
            self.workspace.mkdir(parents=True, exist_ok=True)
            self.process = subprocess.Popen(
                self.command,
                cwd=self.workspace,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
            self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
            self._reader_active = True
            self._stdout_thread.start()
            self._stderr_thread.start()
            try:
                response = self.request(
                    "initialize",
                    {
                        "clientInfo": {"name": "vectorvein-desktop", "title": "VectorVein"},
                        "capabilities": {"experimentalApi": False, "optOutNotificationMethods": []},
                    },
                )
                self._protocol_version = response["protocolVersion"]
                self._notify("initialized")
                self.request("model/list", {})
                return self.status()
            except Exception:
                self._stop()
                raise

    def status(self) -> dict:
        process = self.process
        connected = process is not None and process.poll() is None and self._reader_active and bool(self._protocol_version)
        return {
            "connected": connected,
            "pid": process.pid if connected and process else None,
            "protocol_version": self._protocol_version if connected else "",
        }

    def request(self, method: str, params: dict) -> dict:
        process = self.process
        if process is None or process.poll() is not None or process.stdin is None or not self._reader_active:
            raise TaskAgentError("Task Agent engine is not running")
        with self._write_lock:
            self._next_request_id += 1
            request_id = self._next_request_id
            response_queue: queue.Queue[dict] = queue.Queue(maxsize=1)
            with self._pending_lock:
                self._pending[request_id] = response_queue
            try:
                self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
            except Exception:
                with self._pending_lock:
                    self._pending.pop(request_id, None)
                raise
        try:
            response = response_queue.get(timeout=self.timeout)
        except queue.Empty as exc:
            with self._pending_lock:
                self._pending.pop(request_id, None)
            raise TaskAgentError("Task Agent engine did not respond in time") from exc
        if "error" in response:
            error = response["error"]
            raise TaskAgentError("Task Agent engine rejected the request", code=error.get("code"), data=error.get("data") or error.get("message"))
        return response.get("result", {})

    def _notify(self, method: str, params: dict | None = None) -> None:
        payload = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        with self._write_lock:
            self._write(payload)

    def _write(self, payload: dict) -> None:
        process = self.process
        if process is None or process.stdin is None:
            raise TaskAgentError("Task Agent engine is not running")
        try:
            process.stdin.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise TaskAgentError("Task Agent engine disconnected") from exc

    def _read_stdout(self) -> None:
        process = self.process
        if process is None or process.stdout is None:
            return
        try:
            for line in process.stdout:
                message = json.loads(line)
                request_id = message.get("id")
                if "method" not in message and isinstance(request_id, int):
                    with self._pending_lock:
                        pending = self._pending.pop(request_id, None)
                    if pending is not None:
                        pending.put_nowait(message)
                elif "method" in message:
                    self._observe(message)
        except (ValueError, OSError):
            pass
        finally:
            self._reader_active = False
            self._fail_pending()

    def _drain_stderr(self) -> None:
        process = self.process
        if process is not None and process.stderr is not None:
            for line in process.stderr:
                self._stderr_lines.append(line.rstrip())

    def _fail_pending(self) -> None:
        with self._pending_lock:
            pending = list(self._pending.values())
            self._pending.clear()
        for response_queue in pending:
            response_queue.put_nowait({"error": {"message": " disconnected"}})

    def stop(self) -> None:
        with self._lifecycle_lock:
            self._stop()

    def _stop(self) -> None:
        process = self.process
        if process is None:
            return
        self.process = None
        with self._live_lock:
            self._live.clear()
            self._failures.clear()
        self._protocol_version = ""
        self._reader_active = False
        if process.stdin is not None:
            try:
                process.stdin.close()
            except OSError:
                pass
        if process.poll() is None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()
        current_thread = threading.current_thread()
        for thread in (self._stdout_thread, self._stderr_thread):
            if thread is not None and thread is not current_thread:
                thread.join(timeout=1)
        self._stdout_thread = None
        self._stderr_thread = None
        self._fail_pending()
