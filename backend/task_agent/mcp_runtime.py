from __future__ import annotations

import asyncio
import base64
from contextlib import suppress
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import threading
import time
from typing import Any

import anyio
from vv_agent import FunctionTool
from vv_agent.session.providers import Accepted, Definitive, Outcome, Unknown
from vv_agent.session.records import InboxItem, Record
from vv_agent.tools.base import ToolContext
from vv_agent.types import ToolExecutionResult, ToolResultStatus

from .integrations import (
    mcp_endpoint_fingerprint,
    mcp_schema_digest,
)
from .mcp_library import (
    DEFAULT_TIMEOUT_SECONDS,
    MCPLibrary,
    _classify_transport_error,
    _connection_fingerprint,
    _format_call_tool_result,
    build_mcp_function_tool,
    open_mcp_client,
    redact_mcp_value,
    validate_tool_arguments,
)
from .store import BusinessStore

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
_MIME_EXT_MAP = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/ogg": ".ogg",
    "application/pdf": ".pdf",
    "application/json": ".json",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/csv": ".csv",
}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _canonical_digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_arguments(raw_arguments: Any) -> tuple[dict[str, Any] | None, str | None]:
    if raw_arguments is None or raw_arguments == "":
        return {}, None
    if isinstance(raw_arguments, dict):
        return dict(raw_arguments), None
    if isinstance(raw_arguments, str):
        try:
            parsed = json.loads(raw_arguments)
        except Exception:
            return None, "Tool arguments must be valid JSON."
        if not isinstance(parsed, dict):
            return None, "Tool arguments must be a JSON object."
        return parsed, None
    return None, "Tool arguments must be a JSON object."


def _safe_media_filename(index: int, item: dict[str, Any]) -> str:
    raw_mime = str(item.get("mime_type") or "").split(";", 1)[0].strip().lower()
    ext = _MIME_EXT_MAP.get(raw_mime, ".bin")
    uri = str(item.get("uri") or "").strip()
    stem = ""
    if uri:
        tail = uri.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        if "." in tail:
            tail = tail.rsplit(".", 1)[0]
        tail = _SAFE_FILENAME_RE.sub("_", tail).strip("._-")
        if tail:
            stem = tail[:32]
    if not stem:
        kind = _SAFE_FILENAME_RE.sub("_", str(item.get("kind") or item.get("type") or "artifact")).strip("._-") or "artifact"
        stem = f"{kind}_{index + 1}"
    return f"{index + 1:02d}_{stem}{ext}"


def _materialize_media_items(
    workspace: Path,
    job_id: str,
    media_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not media_items:
        return []
    safe_job_dir = _SAFE_FILENAME_RE.sub("_", str(job_id))[:24] or "job"
    ws_resolved = workspace.resolve()
    out_dir = (ws_resolved / "outputs" / "mcp" / safe_job_dir).resolve()
    if not out_dir.is_relative_to(ws_resolved):
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict[str, Any]] = []
    for idx, item in enumerate(media_items[:16]):
        if not isinstance(item, dict):
            continue
        b64_data = item.get("data_base64") or item.get("data")
        raw_bytes: bytes | None = None
        if isinstance(b64_data, str) and b64_data:
            try:
                raw_bytes = base64.b64decode(b64_data, validate=False)
            except Exception:
                raw_bytes = None
        if raw_bytes is None or len(raw_bytes) == 0 or len(raw_bytes) > 5 * 1024 * 1024:
            continue
        filename = _safe_media_filename(idx, item)
        target = (out_dir / filename).resolve()
        if not target.is_relative_to(out_dir):
            continue
        target.write_bytes(raw_bytes)
        rel_path = target.relative_to(ws_resolved).as_posix()
        artifacts.append(
            {
                "name": filename,
                "path": rel_path,
                "mime_type": str(item.get("mime_type") or "application/octet-stream"),
                "byte_size": len(raw_bytes),
                "sha256": str(item.get("sha256") or hashlib.sha256(raw_bytes).hexdigest()),
                "kind": str(item.get("kind") or item.get("type") or "file"),
            }
        )
    return artifacts


def _untrusted_envelope(
    *,
    server_id: str,
    server_name: str,
    tool_name: str,
    namespaced_name: str,
    formatted_result: dict[str, Any],
    artifacts: list[dict[str, Any]],
    is_error: bool = False,
    error_code: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": not is_error,
        "untrusted_mcp_output": True,
        "trust_boundary": "untrusted_external_mcp_tool_output",
        "server_id": server_id,
        "server_name": server_name,
        "tool_name": tool_name,
        "namespaced_name": namespaced_name,
        "is_error": bool(is_error),
        "text": str(formatted_result.get("text") or ""),
        "structured_content": formatted_result.get("structured_content"),
        "content": list(formatted_result.get("content") or []),
        "truncated": bool(formatted_result.get("truncated")),
    }
    if artifacts:
        payload["artifacts"] = artifacts
    if error_code:
        payload["error_code"] = error_code
    if error_message:
        payload["error"] = error_message
    return payload


def _build_tool_execution_result_dict(
    *,
    tool_call_id: str,
    envelope: dict[str, Any],
    is_error: bool,
    error_code: str | None = None,
) -> dict[str, Any]:
    content_json = json.dumps(envelope, ensure_ascii=False)
    if is_error:
        return ToolExecutionResult(
            tool_call_id=tool_call_id,
            status_code=ToolResultStatus.ERROR,
            error_code=error_code or str(envelope.get("error_code") or "mcp_tool_error"),
            content=content_json,
            metadata={
                "definitive_outcome": True,
                "mcp": {
                    "server_id": envelope.get("server_id"),
                    "tool_name": envelope.get("tool_name"),
                    "namespaced_name": envelope.get("namespaced_name"),
                },
            },
        ).to_dict()
    return ToolExecutionResult(
        tool_call_id=tool_call_id,
        status_code=ToolResultStatus.SUCCESS,
        content=content_json,
        metadata={
            "mcp": {
                "server_id": envelope.get("server_id"),
                "tool_name": envelope.get("tool_name"),
                "namespaced_name": envelope.get("namespaced_name"),
            }
        },
    ).to_dict()


def _unbound(_context: ToolContext, _arguments: Any) -> Any:
    raise RuntimeError("MCP tools require the managed desktop MCP session provider")


def mcp_tools(descriptors: list[dict[str, Any]] | None) -> list[FunctionTool]:
    if not descriptors:
        return []
    tools: list[FunctionTool] = []
    seen: set[str] = set()
    for item in descriptors:
        if not isinstance(item, dict):
            continue
        namespaced = str(item.get("namespaced_name") or item.get("tool_name") or "").strip()
        if not namespaced or namespaced in seen:
            continue
        seen.add(namespaced)
        normalized = dict(item)
        normalized.setdefault("name", str(item.get("remote_tool_name") or item.get("name") or namespaced))
        normalized.setdefault("namespaced_name", namespaced)
        ft = build_mcp_function_tool(normalized, _unbound, needs_approval=True)
        tools.append(ft)
    return tools


@dataclass(slots=True)
class _QueuedOperation:
    job_id: str
    task_id: str
    session_id: str
    turn_id: str
    server_id: str
    server_name: str
    remote_tool_name: str
    namespaced_name: str
    tool_call_id: str
    arguments: dict[str, Any]
    workspace: Path
    server_record: dict[str, Any]
    connection_fp: str
    endpoint_fp: str
    done_event: threading.Event = field(default_factory=threading.Event)
    cancelled_event: threading.Event = field(default_factory=threading.Event)
    dispatched: bool = False


class _ServerConnectionWorker:
    def __init__(
        self,
        *,
        runtime: MCPRuntimeManager,
        key: tuple[str, str, str],
    ) -> None:
        self._runtime = runtime
        self._key = key
        self._queue: asyncio.Queue[_QueuedOperation | None] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self._current_op: _QueuedOperation | None = None
        self._closing = False

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        if self._task is None or self._task.done():
            self._task = loop.create_task(self._run())

    def enqueue(self, op: _QueuedOperation) -> None:
        self._queue.put_nowait(op)

    def cancel_active_step(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()

    async def stop(self) -> None:
        self._closing = True
        self.cancel_active_step()
        await self._queue.put(None)
        if self._task is not None:
            with suppress(Exception, asyncio.CancelledError):
                await self._task

    def _drain_pending_after_connection_loss(self, code: str, message: str) -> None:
        while not self._queue.empty():
            try:
                queued = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if queued is None:
                continue
            if queued.cancelled_event.is_set():
                self._runtime._CancelBeforeDispatch(queued)
            else:
                self._runtime._FinishPreDispatchError(
                    queued,
                    code=code,
                    message=message,
                )

    async def _run(self) -> None:
        current_cm: Any = None
        current_client: Any = None
        current_conn_fp: str | None = None

        async def _close_client() -> None:
            nonlocal current_cm, current_client, current_conn_fp
            cm = current_cm
            current_cm = None
            current_client = None
            current_conn_fp = None
            if cm is not None:
                with suppress(Exception, asyncio.CancelledError):
                    await cm.__aexit__(None, None, None)

        try:
            while not self._closing:
                op = await self._queue.get()
                if op is None:
                    break
                self._current_op = op
                if op.cancelled_event.is_set():
                    self._current_op = None
                    self._runtime._CancelBeforeDispatch(op)
                    continue

                config = op.server_record.get("config") or {}
                secrets = op.server_record.get("secrets") or {}
                raw_timeout = config.get("timeout_seconds", op.server_record.get("timeout_seconds"))
                try:
                    timeout_val = float(raw_timeout) if raw_timeout is not None else float(DEFAULT_TIMEOUT_SECONDS)
                except (TypeError, ValueError):
                    timeout_val = float(DEFAULT_TIMEOUT_SECONDS)
                timeout_s = max(1.0, min(timeout_val, 300.0))

                if current_client is None or current_conn_fp != op.connection_fp:
                    await _close_client()
                    status_tracker: list[int] = []
                    cm = open_mcp_client(op.server_record, status_tracker=status_tracker)
                    try:
                        async with asyncio.timeout(timeout_s):
                            current_client = await cm.__aenter__()
                        current_cm = cm
                        current_conn_fp = op.connection_fp
                    except asyncio.CancelledError:
                        with suppress(Exception, asyncio.CancelledError):
                            await cm.__aexit__(None, None, None)
                        self._runtime._CancelBeforeDispatch(op)
                        if self._closing:
                            break
                        continue
                    except BaseException as exc:
                        with suppress(Exception, asyncio.CancelledError):
                            await cm.__aexit__(None, None, None)
                        classified = _classify_transport_error(
                            exc,
                            secrets=secrets,
                            dispatched=False,
                            last_http_status=status_tracker[-1] if status_tracker else None,
                        )
                        self._runtime._FinishPreDispatchError(
                            op,
                            code=classified.code,
                            message=classified.message,
                        )
                        continue
                if op.cancelled_event.is_set():
                    self._runtime._CancelBeforeDispatch(op)
                    continue

                marked = self._runtime._store.mark_mcp_job_dispatched(op.job_id)
                if not marked:
                    self._runtime._CompleteOperationEvent(op)
                    continue
                op.dispatched = True

                try:
                    with anyio.fail_after(timeout_s):
                        call_res = await current_client.call_tool(
                            op.remote_tool_name,
                            dict(op.arguments or {}),
                            read_timeout_seconds=timeout_s,
                        )
                except TimeoutError:
                    await _close_client()
                    self._runtime._MarkPostDispatchUnknown(
                        op,
                        code="call_timeout",
                        reason="MCP tool call timed out after dispatch; remote outcome is unknown.",
                    )
                    self._runtime._RetireWorker(self._key, self)
                    self._drain_pending_after_connection_loss(
                        "connection_reset_after_unknown",
                        "Previous MCP tool call timed out on this server connection; queued operation was not dispatched.",
                    )
                    break
                except asyncio.CancelledError:
                    await _close_client()
                    self._runtime._MarkPostDispatchUnknown(
                        op,
                        code="cancelled_after_dispatch",
                        reason="MCP tool call was cancelled after dispatch; remote outcome is unknown.",
                    )
                    self._runtime._RetireWorker(self._key, self)
                    self._drain_pending_after_connection_loss(
                        "cancelled",
                        "MCP tool call was cancelled before dispatch.",
                    )
                    break
                except BaseException as exc:
                    await _close_client()
                    classified = _classify_transport_error(
                        exc,
                        secrets=secrets,
                        dispatched=True,
                    )
                    self._runtime._MarkPostDispatchUnknown(
                        op,
                        code=classified.code,
                        reason=f"{classified.message} (after dispatch; remote outcome is unknown).",
                    )
                    self._runtime._RetireWorker(self._key, self)
                    self._drain_pending_after_connection_loss(
                        "connection_reset_after_unknown",
                        "Previous MCP tool call failed after dispatch on this server connection; queued operation was not dispatched.",
                    )
                    break
                finally:
                    self._current_op = None

                try:
                    formatted = _format_call_tool_result(
                        call_res,
                        secrets=secrets,
                        include_internal_media=True,
                    )
                    media_items = formatted.pop("internal_media", None) or []
                    artifacts = _materialize_media_items(op.workspace, op.job_id, media_items)
                    is_err = bool(formatted.get("is_error"))
                    envelope = _untrusted_envelope(
                        server_id=op.server_id,
                        server_name=op.server_name,
                        tool_name=op.remote_tool_name,
                        namespaced_name=op.namespaced_name,
                        formatted_result=formatted,
                        artifacts=artifacts,
                        is_error=is_err,
                        error_code="mcp_tool_error" if is_err else None,
                        error_message=(
                            str(formatted.get("text") or "MCP tool returned an error.")
                            if is_err
                            else None
                        ),
                    )
                    result_dict = _build_tool_execution_result_dict(
                        tool_call_id=op.tool_call_id,
                        envelope=envelope,
                        is_error=is_err,
                        error_code="mcp_tool_error" if is_err else None,
                    )
                    p_updates: dict[str, Any] = {}
                    if artifacts:
                        p_updates["artifacts"] = artifacts
                    if is_err:
                        p_updates["error_code"] = "mcp_tool_error"
                    self._runtime._store.finish_mcp_job(
                        op.job_id,
                        "FAILED" if is_err else "FINISHED",
                        result_dict,
                        payload_updates=p_updates or None,
                    )
                except Exception:
                    self._runtime._MarkPostDispatchUnknown(
                        op,
                        code="result_processing_failed",
                        reason="MCP tool call returned a response that could not be safely recorded.",
                    )
                finally:
                    self._runtime._CompleteOperationEvent(op)
        finally:
            self._runtime._RetireWorker(self._key, self)
            await _close_client()


class MCPRuntimeManager:
    def __init__(self, task_root: Path, *, store: BusinessStore | None = None) -> None:
        self._root = Path(task_root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._store = store or BusinessStore(self._root / "tasks.db")
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._workers: dict[tuple[str, str, str], _ServerConnectionWorker] = {}
        self._operations: dict[str, _QueuedOperation] = {}
        self._closed = False

    @property
    def store(self) -> BusinessStore:
        return self._store

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._closed:
                raise RuntimeError("MCPRuntimeManager is shut down.")
            if self._loop is not None and self._thread is not None and self._thread.is_alive():
                return self._loop
            ready = threading.Event()
            loop_holder: list[asyncio.AbstractEventLoop] = []

            def _runner() -> None:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop_holder.append(loop)
                ready.set()
                try:
                    loop.run_forever()
                finally:
                    pending = asyncio.all_tasks(loop)
                    for t in pending:
                        t.cancel()
                    if pending:
                        with suppress(Exception):
                            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    loop.close()

            thread = threading.Thread(
                target=_runner,
                name="vv-mcp-runtime-loop",
                daemon=True,
            )
            thread.start()
            ready.wait(timeout=5.0)
            if not loop_holder:
                raise RuntimeError("Failed to start MCP runtime event loop.")
            self._loop = loop_holder[0]
            self._thread = thread
            return self._loop

    def enqueue(self, op: _QueuedOperation) -> _QueuedOperation:
        loop = self._ensure_loop()
        with self._lock:
            existing = self._operations.get(op.job_id)
            if existing is not None:
                return existing
            self._operations[op.job_id] = op
            key = (op.task_id, op.session_id, op.server_id)

            def _schedule() -> None:
                worker = self._workers.get(key)
                if worker is None or worker._closing or (worker._task is not None and worker._task.done()):
                    worker = _ServerConnectionWorker(runtime=self, key=key)
                    self._workers[key] = worker
                    worker.start(loop)
                worker.enqueue(op)

            loop.call_soon_threadsafe(_schedule)
            return op

    def get_operation(self, job_id: str) -> _QueuedOperation | None:
        with self._lock:
            return self._operations.get(job_id)

    def _RetireWorker(self, key: tuple[str, str, str], worker: _ServerConnectionWorker) -> None:
        with self._lock:
            if self._workers.get(key) is worker:
                self._workers.pop(key, None)

    def _CompleteOperationEvent(self, op: _QueuedOperation) -> None:
        op.done_event.set()
        with self._lock:
            if self._operations.get(op.job_id) is op:
                self._operations.pop(op.job_id, None)

    def _CancelBeforeDispatch(self, op: _QueuedOperation) -> None:
        try:
            envelope = _untrusted_envelope(
                server_id=op.server_id,
                server_name=op.server_name,
                tool_name=op.remote_tool_name,
                namespaced_name=op.namespaced_name,
                formatted_result={"text": "MCP tool call was cancelled before dispatch.", "content": []},
                artifacts=[],
                is_error=True,
                error_code="tool_cancelled",
                error_message="MCP tool call was cancelled before dispatch.",
            )
            result_dict = _build_tool_execution_result_dict(
                tool_call_id=op.tool_call_id,
                envelope=envelope,
                is_error=True,
                error_code="tool_cancelled",
            )
            self._store.cancel_admitted_mcp_job(op.job_id, result_dict)
        finally:
            self._CompleteOperationEvent(op)

    def _FinishPreDispatchError(self, op: _QueuedOperation, *, code: str, message: str) -> None:
        try:
            envelope = _untrusted_envelope(
                server_id=op.server_id,
                server_name=op.server_name,
                tool_name=op.remote_tool_name,
                namespaced_name=op.namespaced_name,
                formatted_result={"text": message, "content": []},
                artifacts=[],
                is_error=True,
                error_code=code,
                error_message=message,
            )
            result_dict = _build_tool_execution_result_dict(
                tool_call_id=op.tool_call_id,
                envelope=envelope,
                is_error=True,
                error_code=code,
            )
            self._store.finish_mcp_job(
                op.job_id,
                "CANCELLED" if code == "cancelled" else "FAILED",
                result_dict,
                payload_updates={"error_code": code},
            )
        finally:
            self._CompleteOperationEvent(op)

    def _MarkPostDispatchUnknown(self, op: _QueuedOperation, *, code: str, reason: str) -> None:
        try:
            self._store.mark_mcp_job_unknown(op.job_id, reason, code=code)
        finally:
            self._CompleteOperationEvent(op)

    def cancel_job(self, job_id: str) -> None:
        op = self.get_operation(job_id)
        if op is not None:
            op.cancelled_event.set()
            key = (op.task_id, op.session_id, op.server_id)
            loop = self._loop
            if loop is not None and loop.is_running():
                def _abort_if_active() -> None:
                    worker = self._workers.get(key)
                    if worker is not None and worker._current_op is op:
                        worker.cancel_active_step()

                loop.call_soon_threadsafe(_abort_if_active)
            op.done_event.wait(timeout=1.5)

        job = self._store.mcp_job(job_id)
        if job is None:
            return
        status = str(job.get("status") or "").upper()
        payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
        if status == "ADMITTED" and not payload.get("dispatched"):
            envelope = _untrusted_envelope(
                server_id=str(job.get("server_id") or ""),
                server_name=str(payload.get("server_name") or job.get("server_id") or ""),
                tool_name=str(payload.get("remote_tool_name") or job.get("tool_name") or ""),
                namespaced_name=str(payload.get("namespaced_name") or job.get("tool_name") or ""),
                formatted_result={"text": "MCP tool call was cancelled before dispatch.", "content": []},
                artifacts=[],
                is_error=True,
                error_code="tool_cancelled",
                error_message="MCP tool call was cancelled before dispatch.",
            )
            result_dict = _build_tool_execution_result_dict(
                tool_call_id=str(payload.get("tool_call_id") or ""),
                envelope=envelope,
                is_error=True,
                error_code="tool_cancelled",
            )
            self._store.cancel_admitted_mcp_job(job_id, result_dict)
        elif status == "DISPATCHING" or payload.get("dispatched") or payload.get("dispatch_uncertain"):
            self._store.mark_mcp_job_unknown(
                job_id,
                "MCP tool call was cancelled after dispatch; remote outcome is unknown.",
                code="cancelled_after_dispatch",
            )

    def on_event(self, event: Any) -> None:
        etype = getattr(event, "type", None)
        session_id = str(getattr(event, "session_id", "") or "").strip()
        run_id = str(getattr(event, "run_id", "") or "").strip()
        task_id = session_id.split("/child/", 1)[0] if "/child/" in session_id else session_id
        if etype in {"run_completed", "run_failed", "run_cancelled"}:
            if not task_id:
                return
            if "/child/" in session_id:
                self.close_task(task_id, session_id=session_id, expected_turn_id=run_id or None)
            else:
                self.close_task(task_id, expected_turn_id=run_id or None)
        elif etype == "sub_run_completed":
            child_sid = str(getattr(event, "child_session_id", "") or "").strip()
            if task_id and child_sid:
                self.close_task(task_id, session_id=child_sid)

    def close_task(
        self,
        task_id: str,
        *,
        session_id: str | None = None,
        expected_turn_id: str | None = None,
    ) -> None:
        tid = str(task_id or "").strip()
        if not tid:
            return
        with self._lock:
            loop = self._loop
            if expected_turn_id is not None:
                has_newer_active = any(
                    op.task_id == tid
                    and (session_id is None or op.session_id == session_id)
                    and op.turn_id
                    and op.turn_id != expected_turn_id
                    and not op.done_event.is_set()
                    for op in self._operations.values()
                )
                if has_newer_active:
                    return
            matching_ops = [
                op
                for op in self._operations.values()
                if op.task_id == tid and (session_id is None or op.session_id == session_id)
            ]
            for op in matching_ops:
                op.cancelled_event.set()
            if loop is None or not loop.is_running():
                return
            keys = [
                k
                for k in list(self._workers.keys())
                if k[0] == tid and (session_id is None or k[1] == session_id)
            ]

        if not keys:
            return

        async def _stop_keys() -> None:
            workers_to_stop: list[_ServerConnectionWorker] = []
            for k in keys:
                with self._lock:
                    w = self._workers.pop(k, None)
                if w is not None:
                    workers_to_stop.append(w)
            if workers_to_stop:
                await asyncio.gather(*(w.stop() for w in workers_to_stop), return_exceptions=True)

        fut = asyncio.run_coroutine_threadsafe(_stop_keys(), loop)
        with suppress(Exception):
            fut.result(timeout=5.0)

    def shutdown(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            loop = self._loop
            thread = self._thread
            for op in self._operations.values():
                op.cancelled_event.set()

        if loop is not None and loop.is_running():
            async def _stop_all() -> None:
                with self._lock:
                    workers = list(self._workers.values())
                    self._workers.clear()
                if workers:
                    await asyncio.gather(*(w.stop() for w in workers), return_exceptions=True)

            with suppress(Exception):
                fut = asyncio.run_coroutine_threadsafe(_stop_all(), loop)
                fut.result(timeout=5.0)
            with suppress(Exception):
                loop.call_soon_threadsafe(loop.stop)

        if thread is not None and thread.is_alive():
            thread.join(timeout=5.0)


class MCPToolProvider:
    def __init__(
        self,
        task_root: Path,
        task_id: str,
        workspace: Path,
        descriptor: dict[str, Any],
        runtime: MCPRuntimeManager,
        *,
        store: BusinessStore | None = None,
        wait_window_seconds: float = 0.25,
    ) -> None:
        self._root = Path(task_root).resolve()
        self.task_id = str(task_id or "").strip()
        self.workspace = Path(workspace).resolve()
        self.descriptor = dict(descriptor or {})
        self.runtime = runtime
        self.store = store or runtime.store
        self._wait_window_seconds = max(0.0, float(wait_window_seconds))

    def _namespaced_name(self) -> str:
        return str(self.descriptor.get("namespaced_name") or self.descriptor.get("tool_name") or "").strip()

    def _remote_tool_name(self) -> str:
        return str(self.descriptor.get("remote_tool_name") or self.descriptor.get("tool_name") or self.descriptor.get("name") or "").strip()

    @staticmethod
    def _extract_session_id(context: ToolContext) -> str:
        meta = context.metadata if isinstance(context.metadata, dict) else {}
        sid = str(meta.get("session_id") or "").strip()
        if sid:
            return sid
        return str(context.task_id or "default").strip()

    @staticmethod
    def _handle(job: dict[str, Any]) -> dict[str, Any]:
        payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
        return {
            "kind": "provider",
            "provider": str(payload.get("provider") or ""),
            "job_id": str(job.get("job_id") or ""),
            "operation_id": str(payload.get("operation_id") or ""),
            "attempt": int(payload.get("attempt") or 1),
            "request_digest": str(payload.get("request_digest") or ""),
            "evidence": str(payload.get("evidence") or f"mcp-admission:{job.get('job_id')}"),
            "query_ref": str(job.get("job_id") or ""),
            "cancel_ref": str(job.get("job_id") or ""),
        }

    def _job(self, handle: Any) -> dict[str, Any] | None:
        if not isinstance(handle, dict):
            return None
        job_id = handle.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            return None
        job = self.store.mcp_job(job_id)
        if job is None or job.get("task_id") != self.task_id:
            return None
        if self._handle(job) != handle:
            return None
        return job

    def _preflight_validate(
        self,
        arguments: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str | None, str | None]:
        namespaced = self._namespaced_name()
        server_id = str(self.descriptor.get("server_id") or "").strip()
        remote_name = self._remote_tool_name()
        if not namespaced or not server_id or not remote_name:
            return None, "mcp_invalid_descriptor", "Frozen MCP tool descriptor is incomplete."

        task_row = self.store.get_task(self.task_id)
        if task_row is None:
            return None, "mcp_task_missing", "The saved task authorizing this MCP call was not found."
        if task_row is not None:
            snap = task_row.get("config_snapshot")
            if isinstance(snap, dict):
                saved_tools = snap.get("mcp_tools")
                if not isinstance(saved_tools, list):
                    return None, "mcp_not_in_task_snapshot", "Task snapshot does not authorize MCP tools."
                matched_saved: dict[str, Any] | None = None
                for entry in saved_tools:
                    if isinstance(entry, dict) and str(entry.get("namespaced_name") or "") == namespaced:
                        matched_saved = entry
                        break
                if matched_saved is None:
                    return (
                        None,
                        "mcp_tool_not_selected",
                        f"MCP tool '{namespaced}' is not authorized in the frozen task snapshot.",
                    )
                if matched_saved != self.descriptor:
                    return (
                        None,
                        "mcp_descriptor_mismatch",
                        "MCP tool descriptor does not match the saved task snapshot.",
                    )

        server_record = self.store.get_mcp_server(server_id)
        if server_record is None:
            return None, "mcp_server_missing", f"MCP server '{server_id}' no longer exists."
        if not bool(server_record.get("enabled")):
            return None, "mcp_server_disabled", f"MCP server '{server_id}' is currently disabled."
        if MCPLibrary._is_discovery_stale(server_record):
            return (
                None,
                "mcp_discovery_stale",
                f"MCP server '{server_id}' configuration changed or has not passed discovery test.",
            )

        frozen_endpoint_fp = str(self.descriptor.get("endpoint_fingerprint") or "").strip()
        frozen_conn_fp = str(self.descriptor.get("connection_fingerprint") or "").strip()
        current_endpoint_fp = mcp_endpoint_fingerprint(server_record)
        current_conn_fp = _connection_fingerprint(
            server_record["transport"],
            server_record.get("config") or {},
            server_record.get("secrets") or {},
        )
        if frozen_endpoint_fp:
            if current_endpoint_fp != frozen_endpoint_fp:
                return (
                    None,
                    "mcp_endpoint_changed",
                    f"MCP server '{server_id}' destination configuration changed after the task was frozen. Create a new task to use the updated server.",
                )
        elif frozen_conn_fp:
            if current_conn_fp != frozen_conn_fp:
                return (
                    None,
                    "mcp_connection_changed",
                    f"MCP server '{server_id}' configuration changed after the task was frozen. Create a new task to use the updated server.",
                )
        else:
            return (
                None,
                "mcp_snapshot_legacy_unverified",
                f"MCP tool '{namespaced}' snapshot lacks a verifiable server fingerprint. Create a new task to use this tool.",
            )

        tools = server_record.get("tools")
        live_tool: dict[str, Any] | None = None
        if isinstance(tools, list):
            for t in tools:
                if not isinstance(t, dict):
                    continue
                t_ns = str(t.get("namespaced_name") or "")
                t_name = str(t.get("name") or "")
                if t_ns == namespaced or t_name == remote_name:
                    live_tool = t
                    break
        if live_tool is None:
            return (
                None,
                "mcp_tool_missing",
                f"MCP tool '{remote_name}' is no longer present on server '{server_id}'.",
            )
        if not bool(live_tool.get("enabled", True)):
            return (
                None,
                "mcp_tool_disabled",
                f"MCP tool '{remote_name}' on server '{server_id}' is currently disabled.",
            )
        if str(live_tool.get("namespaced_name") or "") != namespaced or str(live_tool.get("name") or "") != remote_name:
            return (
                None,
                "mcp_tool_identity_changed",
                f"MCP tool '{remote_name}' identity on server '{server_id}' no longer matches.",
            )

        frozen_schema = (
            self.descriptor.get("input_schema")
            if isinstance(self.descriptor.get("input_schema"), dict)
            else {"type": "object", "properties": {}}
        )
        live_schema = (
            live_tool.get("input_schema")
            if isinstance(live_tool.get("input_schema"), dict)
            else {"type": "object", "properties": {}}
        )
        frozen_schema_digest = str(self.descriptor.get("schema_digest") or "").strip() or mcp_schema_digest(frozen_schema)
        live_schema_digest = mcp_schema_digest(live_schema)
        if frozen_schema_digest != live_schema_digest:
            return (
                None,
                "mcp_schema_changed",
                f"MCP tool '{remote_name}' schema changed after the task was frozen. Create a new task to use the updated schema.",
            )

        issues = validate_tool_arguments(frozen_schema, dict(arguments or {}))
        if issues:
            return None, "invalid_tool_arguments", "Tool arguments do not match the frozen input schema."

        return server_record, None, None

    def submit(self, plan: Record, *, context: ToolContext) -> Outcome:
        payload = plan.payload
        req = payload.get("request") if isinstance(payload.get("request"), dict) else {}
        tool_call_id = str(req.get("id") or "")
        raw_arguments = req.get("arguments")
        request_digest = str(payload.get("request_digest") or "")
        provider_binding = str(payload.get("provider_binding") or f"mcp:{self._namespaced_name()}")
        session_id = self._extract_session_id(context)
        namespaced = self._namespaced_name()
        server_id = str(self.descriptor.get("server_id") or "").strip()
        server_name = str(self.descriptor.get("server_name") or server_id).strip()
        remote_name = self._remote_tool_name()

        if not request_digest:
            request_digest = _canonical_digest({"tool": namespaced, "arguments": raw_arguments})

        identity = _canonical_digest(
            [
                self.task_id,
                session_id,
                plan.operation_id,
                int(plan.attempt),
                request_digest,
                namespaced,
            ]
        )
        evidence_token = f"mcp-admission:{identity}"

        existing = self.store.mcp_job(identity)
        if existing is not None:
            ex_payload = existing.get("payload") if isinstance(existing.get("payload"), dict) else {}
            if (
                existing.get("task_id") != self.task_id
                or existing.get("session_id") != session_id
                or ex_payload.get("operation_id") != plan.operation_id
                or int(ex_payload.get("attempt") or 0) != int(plan.attempt)
                or ex_payload.get("request_digest") != request_digest
                or ex_payload.get("provider") != provider_binding
                or ex_payload.get("tool_call_id") != tool_call_id
                or ex_payload.get("namespaced_name") != namespaced
            ):
                return Unknown("MCP submission identity conflict")
            return self.query(self._handle(existing))

        parsed_args, parse_err = _parse_arguments(raw_arguments)
        if parsed_args is None:
            envelope = _untrusted_envelope(
                server_id=server_id,
                server_name=server_name,
                tool_name=remote_name,
                namespaced_name=namespaced,
                formatted_result={"text": parse_err or "Invalid arguments.", "content": []},
                artifacts=[],
                is_error=True,
                error_code="invalid_tool_arguments",
                error_message=parse_err or "Invalid arguments.",
            )
            result_dict = _build_tool_execution_result_dict(
                tool_call_id=tool_call_id,
                envelope=envelope,
                is_error=True,
                error_code="invalid_tool_arguments",
            )
            job_payload = {
                "operation_id": plan.operation_id,
                "attempt": int(plan.attempt),
                "request_digest": request_digest,
                "provider": provider_binding,
                "tool_call_id": tool_call_id,
                "turn_id": getattr(plan, "turn_id", None),
                "server_id": server_id,
                "server_name": server_name,
                "remote_tool_name": remote_name,
                "namespaced_name": namespaced,
                "evidence": evidence_token,
                "error_code": "invalid_tool_arguments",
            }
            stored_job, inserted = self.store.admit_mcp_job(
                self.task_id,
                session_id,
                identity,
                server_id,
                namespaced,
                job_payload,
            )
            if inserted:
                self.store.finish_mcp_job(identity, "FAILED", result_dict)
            return self.query(self._handle(stored_job))

        server_record, err_code, err_msg = self._preflight_validate(parsed_args)
        if server_record is None:
            code_str = err_code or "mcp_preflight_failed"
            msg_str = err_msg or "MCP tool preflight validation failed."
            envelope = _untrusted_envelope(
                server_id=server_id,
                server_name=server_name,
                tool_name=remote_name,
                namespaced_name=namespaced,
                formatted_result={"text": msg_str, "content": []},
                artifacts=[],
                is_error=True,
                error_code=code_str,
                error_message=msg_str,
            )
            result_dict = _build_tool_execution_result_dict(
                tool_call_id=tool_call_id,
                envelope=envelope,
                is_error=True,
                error_code=code_str,
            )
            job_payload = {
                "operation_id": plan.operation_id,
                "attempt": int(plan.attempt),
                "request_digest": request_digest,
                "provider": provider_binding,
                "tool_call_id": tool_call_id,
                "turn_id": getattr(plan, "turn_id", None),
                "server_id": server_id,
                "server_name": server_name,
                "remote_tool_name": remote_name,
                "namespaced_name": namespaced,
                "evidence": evidence_token,
                "error_code": code_str,
            }
            stored_job, inserted = self.store.admit_mcp_job(
                self.task_id,
                session_id,
                identity,
                server_id,
                namespaced,
                job_payload,
            )
            if inserted:
                self.store.finish_mcp_job(identity, "FAILED", result_dict)
            return self.query(self._handle(stored_job))

        secrets = server_record.get("secrets") or {}
        safe_args = redact_mcp_value(parsed_args, secrets)
        conn_fp = _connection_fingerprint(
            server_record["transport"],
            server_record.get("config") or {},
            secrets,
        )
        endpoint_fp = mcp_endpoint_fingerprint(server_record)
        job_payload = {
            "operation_id": plan.operation_id,
            "attempt": int(plan.attempt),
            "request_digest": request_digest,
            "provider": provider_binding,
            "tool_call_id": tool_call_id,
            "turn_id": getattr(plan, "turn_id", None),
            "server_id": server_id,
            "server_name": server_name,
            "remote_tool_name": remote_name,
            "namespaced_name": namespaced,
            "evidence": evidence_token,
            "arguments": safe_args,
            "endpoint_fingerprint": endpoint_fp,
        }
        stored_job, inserted = self.store.admit_mcp_job(
            self.task_id,
            session_id,
            identity,
            server_id,
            namespaced,
            job_payload,
        )
        st_payload = stored_job.get("payload") if isinstance(stored_job.get("payload"), dict) else {}
        if (
            stored_job.get("task_id") != self.task_id
            or stored_job.get("session_id") != session_id
            or st_payload.get("operation_id") != plan.operation_id
            or int(st_payload.get("attempt") or 0) != int(plan.attempt)
            or st_payload.get("request_digest") != request_digest
            or st_payload.get("provider") != provider_binding
            or st_payload.get("tool_call_id") != tool_call_id
            or st_payload.get("namespaced_name") != namespaced
        ):
            return Unknown("MCP submission identity conflict")

        handle = self._handle(stored_job)
        if not inserted:
            return self.query(handle)

        op = _QueuedOperation(
            job_id=identity,
            task_id=self.task_id,
            session_id=session_id,
            turn_id=str(getattr(plan, "turn_id", "") or ""),
            server_id=server_id,
            server_name=server_name,
            remote_tool_name=remote_name,
            namespaced_name=namespaced,
            tool_call_id=tool_call_id,
            arguments=parsed_args,
            workspace=self.workspace,
            server_record=server_record,
            connection_fp=conn_fp,
            endpoint_fp=endpoint_fp,
        )
        try:
            queued_op = self.runtime.enqueue(op)
        except Exception:
            envelope = _untrusted_envelope(
                server_id=server_id,
                server_name=server_name,
                tool_name=remote_name,
                namespaced_name=namespaced,
                formatted_result={"text": "MCP runtime is not available.", "content": []},
                artifacts=[],
                is_error=True,
                error_code="runtime_unavailable",
                error_message="MCP runtime is not available.",
            )
            result_dict = _build_tool_execution_result_dict(
                tool_call_id=tool_call_id,
                envelope=envelope,
                is_error=True,
                error_code="runtime_unavailable",
            )
            self.store.finish_mcp_job(identity, "FAILED", result_dict, payload_updates={"error_code": "runtime_unavailable"})
            return self.query(handle)

        if self._wait_window_seconds > 0:
            queued_op.done_event.wait(timeout=self._wait_window_seconds)

        return self.query(handle)

    def query(self, handle: dict[str, Any]) -> Outcome:
        job = self._job(handle)
        if job is None:
            return Unknown("MCP binding not found")
        if job.get("result") is not None:
            return Definitive(job["result"], (handle["evidence"],))

        payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
        status = str(job.get("status") or "").upper()
        if status == "UNKNOWN" or bool(payload.get("dispatch_uncertain")):
            reason = str(
                payload.get("unknown_reason")
                or "MCP tool execution outcome is unknown after dispatch and cannot be safely replayed."
            )
            return Unknown(reason)

        job_id = str(job["job_id"])
        active_op = self.runtime.get_operation(job_id)
        if active_op is not None and not active_op.done_event.is_set():
            return Accepted(handle)

        refreshed = self.store.mcp_job(job_id)
        if refreshed is not None:
            if refreshed.get("result") is not None:
                return Definitive(refreshed["result"], (handle["evidence"],))
            r_payload = refreshed.get("payload") if isinstance(refreshed.get("payload"), dict) else {}
            r_status = str(refreshed.get("status") or "").upper()
            if r_status == "UNKNOWN" or bool(r_payload.get("dispatch_uncertain")):
                reason = str(
                    r_payload.get("unknown_reason")
                    or "MCP tool execution outcome is unknown after dispatch and cannot be safely replayed."
                )
                return Unknown(reason)

        reason = (
            "MCP tool call was in flight when the runtime owner exited; remote outcome is unknown."
            if payload.get("dispatched")
            else "MCP tool job lost its runtime queue owner before completion; remote outcome is unknown."
        )
        self.store.mark_mcp_job_unknown(job_id, reason, code="owner_lost")
        return Unknown(reason)

    def cancel(self, handle: dict[str, Any]) -> Outcome:
        job = self._job(handle)
        if job is None:
            return Unknown("MCP binding not found")
        if job.get("result") is not None:
            return Definitive(job["result"], (handle["evidence"],))
        self.runtime.cancel_job(str(job["job_id"]))
        return self.query(handle)

    def authenticate(self, item: InboxItem, plan: Record) -> bool:
        return False


def mcp_run_views(store: BusinessStore, task_id: str) -> list[dict[str, Any]]:
    jobs = store.mcp_jobs(task_id)
    views: list[dict[str, Any]] = []
    for job in jobs:
        payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
        res = job.get("result") if isinstance(job.get("result"), dict) else {}
        views.append(
            {
                "job_id": str(job.get("job_id") or ""),
                "task_id": str(job.get("task_id") or ""),
                "session_id": str(job.get("session_id") or ""),
                "turn_id": payload.get("turn_id"),
                "tool_call_id": payload.get("tool_call_id"),
                "server_id": str(job.get("server_id") or ""),
                "server_name": str(payload.get("server_name") or job.get("server_id") or ""),
                "tool_name": str(payload.get("remote_tool_name") or job.get("tool_name") or ""),
                "namespaced_name": str(payload.get("namespaced_name") or job.get("tool_name") or ""),
                "status": str(job.get("status") or ""),
                "created_at": job.get("created_at"),
                "updated_at": job.get("updated_at"),
                "dispatched": bool(payload.get("dispatched")),
                "dispatched_at": payload.get("dispatched_at"),
                "dispatch_uncertain": bool(payload.get("dispatch_uncertain")),
                "unknown_code": payload.get("unknown_code"),
                "unknown_reason": payload.get("unknown_reason"),
                "error_code": payload.get("error_code") or res.get("error_code"),
                "artifacts": list(payload.get("artifacts") or []),
            }
        )
    return views
