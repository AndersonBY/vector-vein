"""Windows implementations of the existing Bash and background-command tool contract."""

from __future__ import annotations

import atexit
import os
import tempfile
import threading
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vv_agent.runtime.processes import snapshot_captured_output
from vv_agent.runtime.shell import prepare_shell_execution
from vv_agent.tools.handlers.background import background_command_result
from vv_agent.tools.handlers.common import builtin_error
from vv_agent.types import ToolResultStatus, ToolArtifactRef
from vv_agent.workspace.artifacts import (
    BoundedTextPreview,
    bounded_captured_text_preview,
    persist_captured_text_artifact,
)

from .windows_job import WindowsJob

TERMINAL = {"completed", "failed", "timeout", "stopped"}
BLOCKED_COMMANDS = (
    "rm -rf /",
    "shutdown",
    "reboot",
    "mkfs",
    "dd if=/dev/zero of=/dev/",
)


@dataclass
class Command:
    session_id: str
    owner: str
    root_turn: str
    workspace: Path
    job: WindowsJob
    capture: Path
    shell: str | None
    started: float
    timeout: int | None
    status: str = "running"
    stop_reason: str | None = None
    exit_code: int | None = None
    finished: float | None = None
    observation_error: str | None = None
    preview: BoundedTextPreview | None = None
    artifact: ToolArtifactRef | None = None
    lock: Any = field(default_factory=threading.Lock)
    output_lock: Any = field(default_factory=threading.Lock)
    done: threading.Event = field(default_factory=threading.Event)


class WindowsCommands:
    def __init__(self):
        self.sessions = {}
        self.lock = threading.Lock()
        self.closed = False
        self.cancelled_turns = set()

    @staticmethod
    def root_turn(context):
        return context.task_metadata.get("parent_run_id") or context.task_id

    def run(self, context, arguments):
        command = arguments.get("command", "")
        if not isinstance(command, str) or not command.strip():
            return builtin_error("`command` is required", "command_required")
        if "\0" in command:
            return builtin_error(
                "Command contains a null character", "invalid_tool_arguments"
            )
        if any(snippet in command.lower() for snippet in BLOCKED_COMMANDS):
            return builtin_error("Dangerous command blocked", "dangerous_command")
        delay = arguments.get("yield_time_ms", 1000)
        timeout = arguments.get("timeout_seconds")
        if (
            type(delay) is not int
            or not 0 <= delay <= 10000
            or (
                "timeout_seconds" in arguments
                and (type(timeout) is not int or not 1 <= timeout <= 86400)
            )
        ):
            return builtin_error(
                "Invalid command wait or timeout", "invalid_tool_arguments"
            )
        try:
            cwd = context.resolve_workspace_path(str(arguments.get("exec_dir", ".")))
        except ValueError:
            return builtin_error(
                "Execution directory is outside the task workspace",
                "path_escapes_workspace",
            )
        if not cwd.is_dir():
            return builtin_error(
                "Execution directory does not exist", "invalid_exec_dir"
            )
        runtime = getattr(context.ctx, "metadata", None) or {}
        defaults = {**context.task_metadata, **runtime}
        shell = defaults.get("bash_shell")
        extra_env = defaults.get("bash_env") or {}
        try:
            if shell is not None and not isinstance(shell, str):
                raise ValueError()
            if not isinstance(extra_env, dict):
                raise ValueError()
            argv, stdin = prepare_shell_execution(
                command,
                auto_confirm=bool(arguments.get("auto_confirm", False)),
                stdin=str(arguments["stdin"])
                if arguments.get("stdin") is not None
                else None,
                shell=shell,
                windows_shell_priority=defaults.get("windows_shell_priority"),
            )
            env = dict(os.environ)
            env.setdefault("PYTHONUTF8", "1")
            env.setdefault("PYTHONIOENCODING", "utf-8")
            env.update(
                {
                    str(key): "" if value is None else str(value)
                    for key, value in extra_env.items()
                }
            )
        except (ValueError, TypeError):
            return builtin_error(
                "Configured shell or environment is invalid", "invalid_shell_config"
            )
        token = getattr(context.ctx, "cancellation_token", None)
        if token is not None:
            token.check()
        capture = None
        job = None
        session = None
        try:
            with self.lock:
                root_turn = self.root_turn(context)
                if self.closed or root_turn in self.cancelled_turns:
                    return builtin_error(
                        "Command execution was cancelled", "command_cancelled"
                    )
                started = time.monotonic()
                with (
                    tempfile.NamedTemporaryFile(
                        mode="w+b", delete=False, prefix="vv_desktop_command_"
                    ) as output,
                    tempfile.TemporaryFile(mode="w+b") as input_file,
                ):
                    capture = Path(output.name)
                    if stdin is not None:
                        input_file.write(stdin.encode("utf-8"))
                        input_file.flush()
                        input_file.seek(0)
                    job = WindowsJob(
                        argv,
                        cwd=cwd,
                        stdin_file=input_file,
                        output_file=output,
                        env=env,
                    )
                session = Command(
                    "bg_" + uuid.uuid4().hex,
                    context.task_id,
                    root_turn,
                    context.workspace.resolve(),
                    job,
                    capture,
                    shell,
                    started,
                    timeout,
                )
                threading.Thread(
                    target=self._watch,
                    args=(session,),
                    daemon=True,
                    name="desktop-command-watch",
                ).start()
                self.sessions[session.session_id] = session
        except Exception:
            if session is not None:
                with session.lock:
                    session.done.set()
                    job.close()
            elif job:
                job.close()
            if capture:
                with suppress(OSError):
                    capture.unlink(missing_ok=True)
            if job:
                return builtin_error(
                    "Command supervision failed after launch; outcome is unknown, do not rerun automatically",
                    "command_outcome_unknown",
                )
            return builtin_error(
                "The configured shell could not be started under Windows process supervision",
                "command_start_failed",
            )
        if token is not None:
            token.on_cancel(
                lambda: (
                    self._stop(session, "stopped")
                    if token.reason != "suspend"
                    else None
                )
            )
        session.done.wait(delay / 1000)
        return self._result(session, context)

    def _advance(self, session):
        with session.lock:
            if session.status in TERMINAL or session.done.is_set():
                return
            try:
                code = session.job.poll()
                if code is not None:
                    session.exit_code = code
                    session.status = session.stop_reason or (
                        "completed" if code == 0 else "failed"
                    )
                    session.finished = time.monotonic()
                    session.observation_error = None
                    session.job.close()
                    session.done.set()
                    return
                session.status = "stopping" if session.stop_reason else "running"
                session.observation_error = None
            except OSError:
                session.status = "unknown"
                session.observation_error = (
                    "Windows process status could not be confirmed"
                )
            if (
                session.timeout is not None
                and time.monotonic() - session.started >= session.timeout
            ):
                session.stop_reason = session.stop_reason or "timeout"
                try:
                    session.job.stop()
                    session.status = "stopping"
                except OSError:
                    session.status = "unknown"
                    session.observation_error = (
                        "Windows process termination could not be confirmed"
                    )

    def _watch(self, session):
        while not session.done.is_set():
            self._advance(session)
            session.done.wait(0.05)

    def _stop(self, session, reason):
        self._advance(session)
        with session.lock:
            if session.status in TERMINAL or session.done.is_set():
                return
            session.stop_reason = session.stop_reason or reason
            try:
                session.job.stop()
                session.status = "stopping"
            except OSError:
                session.status = "unknown"
                session.observation_error = (
                    "Windows process termination could not be confirmed"
                )

    def _result(self, session, context):
        self._advance(session)
        artifact_task_id = str(getattr(context.workspace_backend, "task_id", context.task_id))
        # Capture I/O never blocks the watchdog's process timeout/termination checks.
        with session.output_lock:
            with session.lock:
                payload = {
                    "session_id": session.session_id,
                    "status": session.status,
                    "shell": session.shell,
                    "elapsed_seconds": round(
                        (session.finished or time.monotonic()) - session.started, 2
                    ),
                }
                if session.exit_code is not None:
                    payload["exit_code"] = session.exit_code
                if session.observation_error:
                    payload["observation_error"] = session.observation_error
            try:
                if payload["status"] in TERMINAL:
                    if session.preview is None:
                        session.preview = bounded_captured_text_preview(session.capture)
                    preview = session.preview
                    if preview.truncated and session.artifact is None:
                        session.artifact = persist_captured_text_artifact(
                            context.workspace_backend,
                            artifact_task_id,
                            context.tool_call_id,
                            session.capture,
                        )
                    artifact = session.artifact
                    with suppress(OSError):
                        session.capture.unlink(missing_ok=True)
                else:
                    with snapshot_captured_output(session.capture) as snapshot:
                        preview = bounded_captured_text_preview(snapshot)
                        artifact = (
                            persist_captured_text_artifact(
                                context.workspace_backend,
                                artifact_task_id,
                                context.tool_call_id,
                                snapshot,
                            )
                            if preview.truncated
                            else None
                        )
                payload.update(
                    output=preview.content,
                    output_truncated=preview.truncated,
                    output_json_bytes=preview.json_bytes,
                )
                if preview.truncated:
                    payload.update(
                        output_original_bytes=preview.original_bytes,
                        output_visible_bytes=preview.visible_bytes,
                        artifact=artifact.to_dict(),
                    )
            except Exception:
                payload["output_error"] = (
                    "Command output could not be retained; check this session again"
                )
        result = background_command_result(payload, force_handle=True)
        if payload["status"] == "stopped" and not payload.get("output_error"):
            result.status_code, result.error_code = ToolResultStatus.SUCCESS, None
        return result

    def manage(self, context, arguments, *, stop=False):
        identifier = arguments.get("session_id")
        if not isinstance(identifier, str) or not identifier.strip():
            return builtin_error("`session_id` is required", "session_id_required")
        with self.lock:
            session = self.sessions.get(identifier)
        if session is None:
            return builtin_error(
                "Command handle is unavailable in this application session; do not rerun an uncertain command automatically",
                "background_session_missing",
            )
        if (
            session.owner != context.task_id
            or session.workspace != context.workspace.resolve()
        ):
            return builtin_error(
                "Command belongs to a different task or workspace",
                "background_session_forbidden",
            )
        if stop:
            self._stop(session, "stopped")
            session.done.wait(1)
        return self._result(session, context)

    def check(self, context, arguments):
        return self.manage(context, arguments)

    def stop(self, context, arguments):
        return self.manage(context, arguments, stop=True)

    def on_event(self, event):
        if event.type != "run_cancelled":
            return
        with self.lock:
            self.cancelled_turns.add(event.run_id)
            sessions = [
                s for s in self.sessions.values() if s.root_turn == event.run_id
            ]
        for session in sessions:
            self._stop(session, "stopped")

    def shutdown(self):
        with self.lock:
            self.closed = True
            sessions = list(self.sessions.values())
        for session in sessions:
            self._stop(session, "stopped")
        deadline = time.monotonic() + 2
        for session in sessions:
            session.done.wait(max(0, deadline - time.monotonic()))
            with session.lock:
                session.job.close()
                session.done.set()
            with session.output_lock, suppress(OSError):
                session.capture.unlink(missing_ok=True)


command_manager = WindowsCommands()
atexit.register(command_manager.shutdown)
