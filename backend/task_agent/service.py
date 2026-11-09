"""Desktop task lifecycle, durable projections and App Server process ownership."""
from __future__ import annotations

import json
import queue
import re
import shutil
import threading
import uuid
from importlib.metadata import version
from pathlib import Path

from .client import AppServerProcess, TaskAgentError
from .config import MAX_CYCLE_LIMIT, build_model_snapshot, current_llm_settings
from .projection import build_timeline
from .store import BusinessStore, now
from .permissions import validate_permission_mode

CLIENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
ACTIVE_STATUSES = {"PENDING", "PROCESSING"}
DEFAULT_PROFILE = {"agent_id": "general", "name": "", "description": "", "instructions": "", "max_cycles": 0, "allow_file_writes": True, "allow_shell": True, "shell": "auto", "allow_sub_agents": True, "permission_mode": "auto", "workflow_ids": [], "skill_ids": [], "mcp_tool_ids": [], "knowledge_base_ids": []}


class TaskConflict(RuntimeError):
    pass


def required_id(value, label: str) -> str:
    if not isinstance(value, str) or not CLIENT_ID.fullmatch(value):
        raise ValueError(f"Invalid {label}")
    return value


def required_text(value, label="text", limit=64 * 1024):
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > limit:
        raise ValueError(f"Invalid {label}")
    return value.strip()


def text_content(value) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


class TaskAgentService:
    def __init__(self, workspace: Path, *, process: AppServerProcess | None = None, data_path: Path | None = None):
        self.workspace = workspace.resolve()
        if data_path is None:
            from utilities.config import config
            data_path = Path(config.data_path).resolve()
        self.task_root = data_path / "task-agent"
        self.store = BusinessStore(self.task_root / "tasks.db")
        self.process = process or AppServerProcess(self.workspace)
        self._lock = threading.RLock()
        self._closed = threading.Event()
        self._worker = None
        self._subscriptions = set()
        self._admission_lock = threading.RLock()
        self._pending_starts = {}
        self._start_queue = queue.Queue()
        self._start_worker = None

    @property
    def scheduler(self):
        from .scheduler import AgentScheduler
        with self._lock:
            if not hasattr(self, "_scheduler"):
                self._scheduler = AgentScheduler(self)
            return self._scheduler

    @property
    def skills_library(self):
        from .skills import SkillsLibrary
        lib = getattr(self, "_skills_library", None)
        if lib is None:
            lib = SkillsLibrary(self.task_root, store=self.store)
            self._skills_library = lib
        return lib

    @property
    def mcp_library(self):
        from .mcp_library import MCPLibrary
        lib = getattr(self, "_mcp_library", None)
        if lib is None:
            lib = MCPLibrary(self.task_root, store=self.store)
            self._mcp_library = lib
        return lib

    def _watch(self):
        while not self._closed.wait(2):
            for task in self.store.watched_tasks():
                if self._closed.is_set():
                    return
                try:
                    self.get_task(task["tid"])
                except (TaskAgentError, OSError, ValueError, KeyError):
                    pass

    def _start_watching(self):
        if self._worker is not None:
            return
        with self._lock:
            if self._worker is None:
                self._worker = threading.Thread(target=self._watch, daemon=True, name="task-agent-projection")
                self._worker.start()

    def status(self) -> dict:
        self._start_watching()
        return {**self.process.start(), "engine_version": version("vv-agent"), "contract_version": "32.1.1", "session_store": "sqlite"}

    def stop(self) -> None:
        self._closed.set()
        if hasattr(self, "_scheduler"):
            self._scheduler.stop()
        with self._admission_lock:
            while True:
                try:
                    tid = self._start_queue.get_nowait()
                except queue.Empty:
                    break
                if tid is not None:
                    self._record_start_failure(tid, TaskAgentError("Service stopped before task startup"))
                    self._finish_start(tid)
            self._start_queue.put(None)
        self.process.stop()
        for worker in (self._start_worker, self._worker):
            if worker is not None and worker is not threading.current_thread():
                worker.join(timeout=2)

    def _task_workspace(self, tid: str) -> Path:
        from .projects import task_roots
        tid = required_id(tid, "task ID")
        task = self.store.get_task(tid)
        return task_roots(self.task_root, tid, task["config_snapshot"] if task else {})[0]

    @staticmethod
    def _copy_attachments(workspace: Path, attachments: list, *, task_id=None) -> list[dict]:
        if not isinstance(attachments, list) or len(attachments) > 10:
            raise ValueError("A task accepts at most 10 attachments")
        if not attachments:
            return []
        inputs = workspace / "inputs"
        if task_id:
            inputs /= task_id
        if not inputs.resolve().is_relative_to(workspace.resolve()):
            raise ValueError("Attachment directory escapes workspace")
        inputs.mkdir(parents=True, exist_ok=True)
        copied = []
        for value in attachments:
            source = Path(value)
            if not source.is_file() or source.stat().st_size > 50 * 1024 * 1024:
                raise ValueError("Attachments must be existing files of at most 50 MiB each")
            destination = inputs / source.name
            suffix = 1
            while destination.exists():
                destination = inputs / f"{source.stem}-{suffix}{source.suffix}"
                suffix += 1
            shutil.copy2(source, destination)
            copied.append({"name": destination.name, "path": destination.relative_to(workspace).as_posix()})
        return copied

    def list_profiles(self):
        return [self.get_profile("general"), *[{"allow_shell": False, "shell": "auto", "allow_sub_agents": False, "skill_ids": [], "mcp_tool_ids": [], "knowledge_base_ids": [], **p} for p in self.store.profiles() if p["agent_id"] != "general"]]

    def get_profile(self, agent_id):
        agent_id = required_id(agent_id, "agent ID")
        if agent_id == "general":
            return {**DEFAULT_PROFILE, **(self.store.get_profile(agent_id) or {})}
        profile = self.store.get_profile(agent_id)
        if profile is None:
            raise KeyError(agent_id)
        return {"allow_shell": False, "shell": "auto", "allow_sub_agents": False, "skill_ids": [], "mcp_tool_ids": [], "knowledge_base_ids": [], **profile}

    def save_profile(self, payload):
        agent_id = required_id(payload.get("agent_id"), "agent ID")
        name = required_text(payload.get("name"), "name", 160)
        instructions = payload.get("instructions", "")
        if agent_id != "general" or instructions != "":
            instructions = required_text(instructions, "instructions", 32768)
        cycles = payload.get("max_cycles", 0)
        writes = payload.get("allow_file_writes", True)
        permission_mode = validate_permission_mode(payload.get("permission_mode", "auto"))
        shell_enabled = payload.get("allow_shell", False)
        sub_agents = payload.get("allow_sub_agents", False)
        shell = payload.get("shell", "auto")
        if not isinstance(shell_enabled, bool) or not isinstance(sub_agents, bool) or shell not in ("auto", "bash", "git-bash", "pwsh", "powershell"):
            raise ValueError("Invalid agent tool settings")
        description = payload.get("description", "")
        if type(cycles) is not int or not 0 <= cycles <= MAX_CYCLE_LIMIT or not isinstance(writes, bool):
            raise ValueError("Invalid agent limits")
        if not isinstance(description, str) or len(description) > 1000:
            raise ValueError("Invalid description")
        from .workflows import selected_workflows
        from .integrations import selected_mcp_tools, selected_skills
        workflow_ids = payload.get("workflow_ids", [])
        selected_workflows(workflow_ids)
        skill_ids = payload.get("skill_ids", [])
        selected_skills(self.task_root, self.store, skill_ids)
        mcp_tool_ids = payload.get("mcp_tool_ids", [])
        selected_mcp_tools(self.task_root, self.store, mcp_tool_ids)
        from .knowledge import selected_bases
        knowledge_base_ids = payload.get("knowledge_base_ids", [])
        selected_bases(knowledge_base_ids)
        provider, model = payload.get("model_provider", ""), payload.get("model", "")
        effort = payload.get("reasoning_effort", "default")
        if not isinstance(provider, str) or not isinstance(model, str):
            raise ValueError("Invalid agent model")
        if provider or model:
            llm_settings = current_llm_settings()
            model_snapshot = build_model_snapshot(llm_settings, provider, model, effort)
            if llm_settings["backends"][model_snapshot["backend"]]["models"][model].get("enabled") is False:
                raise ValueError("Selected model is disabled")
        elif effort != "default":
            raise ValueError("Choose a model before setting reasoning effort")
        previous = self.store.get_profile(agent_id)
        timestamp = now()
        profile = dict(agent_id=agent_id, name=name, instructions=instructions, description=description.strip(), max_cycles=cycles, allow_file_writes=writes, allow_shell=shell_enabled, shell=shell, allow_sub_agents=sub_agents, permission_mode=permission_mode, workflow_ids=workflow_ids, skill_ids=list(skill_ids), mcp_tool_ids=list(mcp_tool_ids), knowledge_base_ids=list(knowledge_base_ids))
        profile.update(model_provider=provider, model=model, reasoning_effort=effort,
                       created_at=(previous or {}).get("created_at") or (previous or {}).get("updated_at") or timestamp,
                       updated_at=timestamp)
        self.store.save_profile(profile)
        return profile

    def _execute(self, tid, command_id, method, params):
        existing = self.store.command(tid, command_id)
        if existing and (existing["method"] != method or existing["params"] != params):
            raise TaskConflict("This request ID already has different content")
        if existing and existing["receipt"] is not None:
            return existing["receipt"]
        self.store.save_command(tid, command_id, method, params)
        if self._closed.is_set():
            raise TaskAgentError("Task service is stopped")
        self.process.start()
        if self._closed.is_set():
            # stop() can win before start() acquires the process lifecycle lock.
            self.process.stop()
            raise TaskAgentError("Task service is stopped")
        result = self.process.request(method, params)
        self.store.complete_command(tid, command_id, result)
        return result

    def _start_pending(self, tid):
        with self._admission_lock:
            return tid in self._pending_starts

    def _require_started(self, tid):
        tid = required_id(tid, "task ID")
        task = self.store.get_task(tid)
        if self._start_pending(tid) or (task and task["status"] == "PENDING"):
            raise TaskConflict("Task startup is pending. Wait or retry startup before continuing.")

    def _record_start_failure(self, tid, error):
        from .config import ConfigError
        from .model_errors import configuration_failure, model_failure
        task = self.store.get_task(tid)
        if task and task["status"] == "PENDING":
            state = self.store.projection(tid)["state"]
            failure = configuration_failure(error) if isinstance(error, ConfigError) else model_failure(error)
            self.store.save_state(tid, {**state, "start_model_failure": failure})

    def _finish_start(self, tid):
        with self._admission_lock:
            finished = self._pending_starts.pop(tid, None)
            if finished is not None:
                finished.set()

    def _run_start(self, tid):
        try:
            self._start_task(tid)
        except Exception as error:
            self._record_start_failure(tid, error)
            raise
        finally:
            self._finish_start(tid)

    def _start_loop(self):
        while True:
            tid = self._start_queue.get()
            if tid is None:
                return
            if not self._start_pending(tid):
                continue
            try:
                self._run_start(tid)
            except Exception:
                # PENDING and the safe diagnosis are durable; retry is explicit.
                continue

    def create_task(self, payload: dict, *, background: bool = False) -> dict:
        with self._admission_lock:
            if self._closed.is_set():
                raise TaskAgentError("Task service is stopped")
            task = self._create_task(payload)
            tid = task["tid"]
            finished = self._pending_starts.get(tid)
            owner = task["status"] == "PENDING" and finished is None
            if owner:
                finished = self._pending_starts[tid] = threading.Event()
            if background:
                if owner:
                    self._start_queue.put(tid)
                    try:
                        if self._start_worker is None or not self._start_worker.is_alive():
                            self._start_worker = threading.Thread(target=self._start_loop, daemon=True,
                                                                  name="task-agent-start")
                            self._start_worker.start()
                    except Exception as error:
                        self._record_start_failure(tid, error)
                        self._finish_start(tid)
                return self.get_task(tid, cached=True)
        # Schedulers retain synchronous completion, without holding the admission lock.
        if owner:
            self._run_start(tid)
        elif finished is not None:
            finished.wait()
        return self.get_task(tid)

    def _create_task(self, payload):
        goal = required_text(payload.get("goal"), "goal")
        tid = required_id(payload.get("input_id"), "task ID")
        provider, model = payload.get("model_provider", ""), payload.get("model", "")
        effort = payload.get("reasoning_effort", "default")
        project_id = payload.get("project_id")
        if project_id == "":
            project_id = None
        if project_id is not None:
            project_id = required_id(project_id, "project ID")
        from .integrations import selected_mcp_tools, selected_skills, validate_mcp_tool_ids_format
        permission_mode = validate_permission_mode(payload["permission_mode"]) if "permission_mode" in payload else None
        has_mcp_override = "mcp_tool_ids" in payload
        explicit_mcp_ids = validate_mcp_tool_ids_format(payload["mcp_tool_ids"]) if has_mcp_override else None
        task = self.store.get_task(tid)
        if task:
            if task.get("project_id") != project_id:
                raise TaskConflict("This task ID already belongs to a different project")
            if (task["goal"], task["model_provider"], task["model"], task["reasoning_effort"]) != (goal, provider, model, effort):
                raise TaskConflict("This task ID already has different content")
            if permission_mode is not None and task["config_snapshot"].get("agent_profile", {}).get("permission_mode") != permission_mode:
                raise TaskConflict("This task ID already has a different permission mode")
            snapshot = task["config_snapshot"]
            if snapshot.get("agent_profile", DEFAULT_PROFILE)["agent_id"] != payload.get("agent_id", "general"):
                raise TaskConflict("This task ID already has a different agent")
            saved_override = snapshot.get("mcp_tool_ids_override")
            if explicit_mcp_ids != saved_override:
                raise TaskConflict("This task ID already has different MCP tool selections")
        else:
            from .projects import project_view, validate_saved_roots
            project = self.store.get_project(project_id) if project_id else None
            if project_id:
                project_view(project)
                validate_saved_roots(project["roots"])
            snapshot = build_model_snapshot(current_llm_settings(), provider, model, effort)
            if project:
                snapshot["project"] = {key: project[key] for key in ("project_id", "name", "roots")}
            profile = self.get_profile(payload.get("agent_id", "general"))
            from .knowledge import selected_bases
            snapshot["knowledge_bases"] = selected_bases(profile.get("knowledge_base_ids", []))
            from .workflows import selected_workflows
            snapshot["workflow_tools"] = selected_workflows(profile.get("workflow_ids", []))
            snapshot["skills"] = selected_skills(self.task_root, self.store, profile.get("skill_ids", []))
            effective_mcp_ids = explicit_mcp_ids if explicit_mcp_ids is not None else list(profile.get("mcp_tool_ids", []))
            snapshot["mcp_tools"] = selected_mcp_tools(self.task_root, self.store, effective_mcp_ids)
            if explicit_mcp_ids is not None:
                snapshot["mcp_tool_ids_override"] = list(explicit_mcp_ids)
            profile = {**profile, "permission_mode": permission_mode or profile.get("permission_mode", "auto"), "mcp_tool_ids": list(effective_mcp_ids)}
            snapshot["agent_profile"] = profile
            from .host import command_shell
            snapshot["command_shell"] = command_shell(profile)
            snapshot["engine_version"] = version("vv-agent")
            turn_input_id = required_id(payload.get("turn_input_id") or f"turn_{uuid.uuid4().hex}", "turn ID")
            workspace = Path(project["roots"][0]) if project else self._task_workspace(tid)
            if not project:
                workspace.mkdir(parents=True, exist_ok=True)
            attachments = self._copy_attachments(workspace, payload.get("attachments", []), task_id=tid if project else None)
            timestamp = now()
            task = dict(tid=tid, thread_id=tid, title=goal.splitlines()[0][:72], goal=goal, status="PENDING",
                        current_turn_id=f"{tid}/turn/{turn_input_id}", model_provider=provider, model=model,
                        reasoning_effort=effort, config_snapshot=snapshot, created_at=timestamp, updated_at=timestamp, project_id=project_id)
            self.store.create_task(task, first_message=dict(task_id=tid, turn_id=task["current_turn_id"], role="user", content=goal,
                                                           status="PENDING", attachments=attachments, created_at=timestamp))
        return task

    def _start_task(self, tid):
        task = self.store.get_task(tid)
        if task is None:
            raise KeyError(tid)
        if task["status"] != "PENDING":
            return
        if self._closed.is_set():
            raise TaskAgentError("Task service is stopped")
        snapshot = task["config_snapshot"]
        message = self.store.list_messages(tid)[0]
        goal, attachments = task["goal"], message["attachments"]
        turn_input_id = message["turn_id"].rsplit("/", 1)[-1]
        if snapshot.get("project"):
            from .projects import validate_saved_roots
            validate_saved_roots(snapshot["project"]["roots"])
        prompt = goal
        if attachments:
            prompt += "\n\nAttachments in the task workspace: " + ", ".join(item["path"] for item in attachments)
        self._execute(tid, "create_thread", "thread/start", {
            "inputId": tid, "agentKey": "desktop-task", "cwd": str(self._task_workspace(tid)),
            "metadata": {"model_snapshot": snapshot},
        })
        started = self._execute(tid, turn_input_id, "turn/start", {
            "threadId": tid, "inputId": turn_input_id, "expectedTurnId": None, "input": [{"type": "text", "text": prompt}],
        })
        self.store.upsert_message(dict(task_id=tid, turn_id=f"{tid}/turn/{turn_input_id}", role="user", content=goal,
                                      status="COMPLETED", attachments=attachments))
        # A replay must not reset an already finished task to Processing.
        if task["status"] == "PENDING":
            self.store.update_task(tid, status="PROCESSING", current_turn_id=started["turnId"])
        state = self.store.projection(tid)["state"]
        if "start_model_failure" in state:
            self.store.save_state(tid, {key: value for key, value in state.items() if key != "start_model_failure"})
        self._start_watching()

    def retry_start(self, tid, *, background: bool = False):
        task = self.store.get_task(required_id(tid, "task ID"))
        if task is None:
            raise KeyError(tid)
        snapshot = task["config_snapshot"]
        retry_payload = {"input_id": tid, "goal": task["goal"], "model_provider": task["model_provider"],
                         "model": task["model"], "reasoning_effort": task["reasoning_effort"],
                         "agent_id": snapshot.get("agent_profile", DEFAULT_PROFILE)["agent_id"], "project_id": task.get("project_id")}
        if "mcp_tool_ids_override" in snapshot:
            retry_payload["mcp_tool_ids"] = list(snapshot["mcp_tool_ids_override"])
        return self.create_task(retry_payload, background=background)

    @staticmethod
    def _projected_status(snapshot: dict) -> str:
        state = snapshot.get("state", {})
        if state.get("status") == "suspended":
            return "PAUSED"
        interaction = state.get("pendingInteraction") or {}
        if interaction.get("kind") == "user":
            return "WAITING_FOR_USER"
        if interaction.get("kind") == "approval":
            return "WAITING_FOR_APPROVAL"
        statuses = {"user_wait": "WAITING_FOR_USER", "approval_wait": "WAITING_FOR_APPROVAL", "suspended": "PAUSED"}
        if state.get("status") in statuses:
            return statuses[state["status"]]
        turns = snapshot.get("turns", [])
        if not turns:
            return "PENDING"
        if turns[-1].get("result", {}).get("completionReason") == "cancelled":
            return "INTERRUPTED"
        return {"completed": "COMPLETED", "failed": "FAILED", "interrupted": "PROCESSING"}.get(turns[-1].get("status"), "PROCESSING")

    def _approval_details(self, tid, state):
        pending = state.get("pendingInteraction")
        if not pending or pending.get("kind") != "approval" or pending.get("sessionId") == tid:
            return state
        previous = self.store.projection(tid)["state"].get("pendingInteraction") or {}
        if previous.get("requestId") == pending["requestId"] and "arguments" in previous:
            return {**state, "pendingInteraction": {**pending, "tool_name": previous["tool_name"], "arguments": previous["arguments"]}}
        # App Server thread IDs exclude native child IDs; use the public SDK event view.
        from vv_agent.session.sqlite import SQLiteStore
        from vv_agent.session.events import SessionRunEventStore
        with SQLiteStore.standalone(str(self.task_root / "sessions.db")) as store:
            planned = {}
            for event in SessionRunEventStore(store, pending["sessionId"]).replay(run_id=pending["turnId"]):
                if event.type == "tool_call_planned":
                    planned[event.tool_call_id] = event.arguments
                elif event.type == "approval_requested" and event.request_id == pending["requestId"]:
                    if event.tool_call_id not in planned:
                        break
                    return {**state, "pendingInteraction": {**pending, "tool_name": event.tool_name, "arguments": planned[event.tool_call_id]}}
        raise ValueError("Approval details are unavailable")

    def _sync(self, task):
        tid = task["tid"]
        from .runtime_settings import apply_pending_change
        apply_pending_change(self.store, self.process, tid)
        task = self.store.get_task(tid)
        process_status = self.process.start()
        subscription = (process_status.get("pid"), tid)
        wait_kind = self.store.projection(tid)["state"].get("waitKind")
        wake_wait = wait_kind == "child" or (wait_kind == "provider" and (task["config_snapshot"].get("workflow_tools") or task["config_snapshot"].get("mcp_tools")))
        method = "thread/resume" if subscription not in self._subscriptions or wake_wait else "thread/read"
        snapshot = self.process.request(method, {"threadId": task["thread_id"]})
        self._subscriptions.add(subscription)
        cursor = self.store.projection(tid)["cursor"]
        params = {"threadId": task["thread_id"], "limit": 256}
        if cursor is not None:
            params["afterCursor"] = cursor
        # Bound one UI refresh; an unfinished page continues from its committed cursor.
        for _ in range(8):
            page = self.process.request("thread/events/list", params)
            self.store.save_event_page(tid, page)
            if not page["more"]:
                break
            params.update(afterCursor=page["nextCursor"], throughCursor=page["throughCursor"])
        for turn in snapshot.get("turns", []):
            output = turn.get("result", {}).get("finalOutput")
            if turn.get("status") == "completed" and output is not None and text_content(output).strip():
                self.store.upsert_message(dict(task_id=tid, turn_id=turn["turnId"], role="assistant", content=text_content(output), status="COMPLETED"))
        self.store.save_state(tid, {**self._approval_details(tid, snapshot.get("state", {})), "history_pending": page["more"]})
        projected = self._projected_status(snapshot)
        from .workflows import workflow_run_views
        if projected == "PROCESSING" and any(run["status"] == "PAUSED" for run in workflow_run_views(self.store, tid)):
            projected = "WAITING_FOR_WORKFLOW"
        if projected == "PROCESSING" and snapshot.get("state", {}).get("waitKind") == "provider" and self.store.mcp_jobs(tid):
            from .mcp_runtime import mcp_run_views
            active_turn = snapshot["turns"][-1]["turnId"] if snapshot.get("turns") else task["current_turn_id"]
            turn_mcp = [r for r in mcp_run_views(self.store, tid) if r.get("turn_id") == active_turn]
            if turn_mcp and any(r["status"] == "UNKNOWN" or r.get("dispatch_uncertain") for r in turn_mcp) and not any(r["status"] in {"ADMITTED", "DISPATCHING"} for r in turn_mcp):
                projected = "FAILED"
        if not snapshot.get("turns") and task["status"] == "FAILED":
            projected = "FAILED"
        projected_turn = snapshot["turns"][-1]["turnId"] if snapshot.get("turns") else task["current_turn_id"]
        self.store.update_task(tid, status=projected, current_turn_id=projected_turn)
        if projected in {"COMPLETED", "FAILED", "INTERRUPTED"} and (task["status"] not in {"COMPLETED", "FAILED", "INTERRUPTED"} or projected_turn != task["current_turn_id"]):
            self.scheduler.complete_task(tid, projected_turn, projected)

    def get_task(self, tid: str, *, cached: bool = False) -> dict:
        sync_error = self._closed.is_set()
        task = self.store.get_task(tid)
        if task is None:
            raise KeyError(tid)
        if not cached and not self._start_pending(tid) and task["status"] != "PENDING":
            with self._lock:
                task = self.store.get_task(tid)
                if task is None:
                    raise KeyError(tid)
                try:
                    if not self._closed.is_set() and not self._start_pending(tid):
                        self._sync(task)
                except (TaskAgentError, OSError, ValueError):
                    sync_error = True
        # First paint reads durable history without waiting on engine startup or its lock.
        task = self.store.get_task(tid)
        if task is None:
            raise KeyError(tid)
        events = self.store.events(tid)
        timeline, todos = build_timeline(events)
        workflow_runs = []
        if self.store.workflow_jobs(tid):
            from .workflows import workflow_run_views
            workflow_runs = workflow_run_views(self.store, tid)
        mcp_runs = []
        if self.store.mcp_jobs(tid):
            from .mcp_runtime import mcp_run_views
            mcp_runs = mcp_run_views(self.store, tid)
        names = {item["tool_name"]: item["title"] for item in task["config_snapshot"].get("workflow_tools", [])}
        for item in task["config_snapshot"].get("mcp_tools", []):
            if isinstance(item, dict) and item.get("namespaced_name"):
                names[item["namespaced_name"]] = f"{item.get('server_name') or item.get('server_id')}: {item.get('title') or item.get('name')}"
        for entry in timeline:
            if entry.get("tool_name") in names:
                entry["display_name"] = names[entry["tool_name"]]
        state = self.store.projection(tid)["state"]
        risk_reviews = self.store.risk_reviews(tid)
        reviews_by_call = {(r["run_id"], r.get("tool_call_id")): r for r in risk_reviews}
        mcp_runs_by_call = {(r.get("turn_id"), r.get("tool_call_id")): r for r in mcp_runs if r.get("tool_call_id")}
        for entry in timeline:
            if entry["kind"] == "tool":
                review = reviews_by_call.get((entry["turn_id"], entry["tool_call_id"]))
                if review:
                    entry["risk_review"] = review
                mcp_run = mcp_runs_by_call.get((entry["turn_id"], entry["tool_call_id"]))
                if mcp_run:
                    entry["mcp_run"] = mcp_run
                    if mcp_run["status"] == "UNKNOWN" or mcp_run.get("dispatch_uncertain"):
                        entry["status"] = "unknown"
                        entry["error_code"] = mcp_run.get("unknown_code") or "tool_outcome_unknown"
        pending = state.get("pendingInteraction")
        if pending and pending.get("kind") == "approval":
            review = next((r for r in risk_reviews if r["request_id"] == pending["requestId"]), None)
            approval_ev = next((e for e in reversed(events) if e.get("kind") == "approval_requested" and e.get("request_id") == pending["requestId"]), None)
            pending_tool = pending.get("tool_name") or pending.get("toolName") or (approval_ev or {}).get("tool_name") or (review or {}).get("tool_name")
            display = names.get(pending_tool) if pending_tool else None
            state = {**state, "pendingInteraction": {**pending, **({"tool_name": pending_tool} if pending_tool and "tool_name" not in pending else {}), **({"display_name": display} if display else {}), "risk_review": review}}
        current_task = self.store.get_task(tid)
        if current_task is None:
            raise KeyError(tid)
        from .model_errors import enrich_failures
        from .integrations import compact_task_view
        from .runtime_settings import public_settings
        from .usage import usage_summary
        model_rejection_only = enrich_failures(timeline, events, self.store.model_failures(tid), current_task["current_turn_id"], state.get("unconfirmedCount", 0))
        recovery_required = current_task["status"] in {"PROCESSING", "PENDING"} and hasattr(self.process, "execution_failed") and self.process.execution_failed(tid, current_task["current_turn_id"])
        live = self.process.live_text(tid) if hasattr(self.process, "live_text") else None
        start_pending = self._start_pending(tid)
        sync_error = sync_error or (current_task["status"] == "PENDING" and not start_pending)
        return {"start_pending": start_pending, "start_model_failure": state.get("start_model_failure"), "task": compact_task_view(self.store.get_task(tid)), "messages": self.store.list_messages(tid), "timeline": timeline,
                "todos": todos, "state": state, "live": live, "sync_error": sync_error or recovery_required, "recovery_required": recovery_required, "workflow_runs": workflow_runs, "mcp_runs": mcp_runs, "model_rejection_only": model_rejection_only, "risk_reviews": risk_reviews,
                "runtime_settings": public_settings(self.store, current_task), "token_usage": usage_summary(events)}

    def update_runtime_settings(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Invalid task request")
        self._require_started(payload.get("task_id"))
        from .runtime_settings import admit_change, apply_pending_change
        with self._lock:
            self._require_started(payload.get("task_id"))
            change = admit_change(self.store, payload)
            if change["receipt"] and not change["receipt"].get("accepted"):
                raise ValueError("Task settings change was rejected")
            if change["receipt"] is None:
                apply_pending_change(self.store, self.process, payload["task_id"])
            return self.get_task(payload["task_id"], cached=True)

    def task_context(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"task_id"}:
            raise ValueError("Invalid task context request")
        tid = required_id(payload.get("task_id"), "task ID")
        task = self.store.get_task(tid)
        if not task:
            raise KeyError(tid)
        self._require_started(tid)
        with self._lock:
            self._require_started(payload.get("task_id"))
            self._sync(task)
        self.process.start()
        result = self.process.request("thread/context/read", {"threadId": task["thread_id"]})
        if not isinstance(result, dict) or not isinstance(result.get("contextVersion"), str):
            raise TaskAgentError("Task context response is unavailable")
        # The popup needs counts and limits, not the retained summary's text.
        last = result.get("lastCompaction")
        if isinstance(last, dict):
            result = {**result, "lastCompaction": {key: last[key] for key in ("seq", "createdAt", "replacedMessageCount") if key in last}}
        from .usage import usage_summary
        events = self.store.events(tid)
        compaction = None
        with self.store.connect() as connection:
            command = connection.execute("SELECT receipt FROM task_commands WHERE task_id=? AND method='thread/compact/start' AND receipt IS NOT NULL ORDER BY rowid DESC LIMIT 1", (tid,)).fetchone()
        if command:
            receipt = json.loads(command["receipt"])
            request_id = receipt.get("requestId")
            if request_id:
                matched = next((event for event in reversed(events) if request_id in event.get("compaction_requests", [])), None)
                status = "failed" if matched and matched.get("compaction_failed") else "completed" if matched and matched["kind"] == "memory_compact_completed" else "running" if matched else "queued"
                compaction = {"request_id": request_id, "status": status}
        return {"context": result, "token_usage": usage_summary(events), "compaction": compaction}

    def compact_context(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"task_id", "action_id", "expected_context_version"}:
            raise ValueError("Invalid context compaction request")
        tid = required_id(payload.get("task_id"), "task ID")
        action_id = required_id(payload.get("action_id"), "compaction action ID")
        expected = payload.get("expected_context_version")
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Invalid context version")
        self._require_started(tid)
        with self._lock:
            self._require_started(payload.get("task_id"))
            task = self.store.get_task(tid)
            if not task:
                raise KeyError(tid)
            result = self._execute(tid, action_id, "thread/compact/start", {"threadId": task["thread_id"], "actionId": action_id, "expectedContextVersion": expected})
            return {"compaction": result}

    def list_tasks(self, limit: int = 20, project_id=None, offset: int = 0, search: str = "", **options) -> dict:
        from .integrations import compact_task_view
        if project_id == "":
            project_id = None
        if project_id is not None:
            required_id(project_id, "project ID")
            self.get_project(project_id)
        self._start_watching()
        queried = self.store.query_tasks(limit, project_id, offset, search, **options)
        queried["tasks"] = [compact_task_view(item) for item in queried["tasks"]]
        return {**queried, "sync_error": False}

    def get_project(self, project_id):
        from .projects import project_view
        return project_view(self.store.get_project(required_id(project_id, "project ID")))

    def list_projects(self):
        from .projects import project_view
        return [project_view(project) for project in self.store.list_projects()]

    def save_project(self, payload):
        from .projects import normalize_roots, project_view, ProjectError
        project_id = required_id(payload.get("project_id"), "project ID")
        roots = normalize_roots(payload.get("roots"))
        name = payload.get("name", "")
        if not isinstance(name, str) or len(name.encode("utf-8")) > 160:
            raise ProjectError("invalid_name")
        name = name.strip() or Path(roots[0]).name or roots[0]
        return project_view(self.store.save_project({"project_id": project_id, "name": name, "roots": roots}, payload.get("expected_updated_at")))

    def delete_task(self, payload):
        from .deletion import DeletionConflict
        with self._lock:
            tid = required_id(payload.get('task_id'), 'task ID')
            task = self.store.get_task(tid)
            if task is None:
                raise KeyError(tid)
            if not isinstance(payload.get('expected_updated_at'), str) or task['updated_at'] != payload['expected_updated_at']:
                raise DeletionConflict('changed')
            return self._delete_tasks([task])

    def set_hidden(self, payload):
        with self._lock:
            tid = required_id(payload.get("task_id"), "task ID")
            hidden = payload.get("hidden")
            if type(hidden) is not bool:
                raise ValueError("Invalid task visibility")
            task = self.store.get_task(tid)
            if not task:
                raise KeyError(tid)
            if payload.get("expected_updated_at") != task["updated_at"]:
                raise TaskConflict("Task changed. Refresh before changing visibility.")
            self.store.update_task(tid, hidden=int(hidden))
            return {"task_id": tid, "hidden": hidden}

    def delete_project(self, payload):
        from .deletion import DeletionConflict
        with self._lock:
            project_id = required_id(payload.get('project_id'), 'project ID')
            project = self.store.get_project(project_id)
            if project is None:
                raise KeyError(project_id)
            if not isinstance(payload.get('expected_updated_at'), str) or project['updated_at'] != payload['expected_updated_at']:
                raise DeletionConflict('changed')
            count = payload.get('expected_task_count')
            if type(count) is not int or count < 0:
                raise ValueError('Expected task count required')
            with self.store.connect() as connection:
                tasks = [self.store._task(row) for row in connection.execute('SELECT * FROM tasks WHERE project_id=?', (project_id,))]
            if len(tasks) != count:
                raise DeletionConflict('changed')
            return self._delete_tasks(tasks, project=project, expected_task_count=count)

    def _delete_tasks(self, tasks, **options):
        from .deletion import delete_history, validate_tasks
        if any(self._start_pending(task["tid"]) for task in tasks):
            from .deletion import DeletionConflict
            raise DeletionConflict("active_task")
        validate_tasks(self.store, tasks)
        result = delete_history(self.store, self.task_root, tasks, **options)
        identities = {task['thread_id'] for task in tasks}
        self._subscriptions = {key for key in self._subscriptions if key[1] not in identities}
        if hasattr(self.process, 'forget_tasks'):
            self.process.forget_tasks(identities)
        return result

    def send_message(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("Invalid task request")
        self._require_started(payload.get("task_id"))
        with self._lock:
            self._require_started(payload.get("task_id"))
            tid = required_id(payload.get("task_id"), "task ID")
            text = required_text(payload.get("text"))
            command_id = required_id(payload.get("input_id"), "turn ID")
            existing = self.store.command(tid, command_id)
            if existing:
                if existing["method"] not in {"turn/steer", "turn/followUp"} or existing["params"]["input"][0]["text"] != text:
                    raise TaskConflict("This request ID already has different content")
                method, params = existing["method"], existing["params"]
            else:
                detail = self.get_task(tid)
                if detail["sync_error"]:
                    raise TaskAgentError("Reconnect before continuing")
                task = detail["task"]
                if task["status"] in {"WAITING_FOR_USER", "WAITING_FOR_APPROVAL", "WAITING_FOR_WORKFLOW", "PAUSED"}:
                    raise TaskConflict("Answer the pending question or resume first")
                method = "turn/steer" if task["status"] in ACTIVE_STATUSES else "turn/followUp"
                params = {"threadId": task["thread_id"], "inputId": command_id, "expectedTurnId": task["current_turn_id"], "input": [{"type": "text", "text": text}]}
            receipt = self._execute(tid, command_id, method, params)
            self.store.upsert_message(dict(task_id=tid, turn_id=f"{tid}/turn/{command_id}", role="user", content=text, status="COMPLETED"))
            if existing is None:
                self.store.update_task(tid, current_turn_id=receipt["turnId"], status="PROCESSING", hidden=0)
            self._start_watching()
            return self.get_task(tid)

    def act(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("Invalid task request")
        self._require_started(payload.get("task_id"))
        with self._lock:
            self._require_started(payload.get("task_id"))
            tid = required_id(payload.get("task_id"), "task ID")
            action_id = required_id(payload.get("action_id"), "action ID")
            turn_id = payload.get("turn_id")
            action = payload.get("action")
            if not isinstance(action, dict) or action.get("kind") not in {"respond", "suspend", "resume", "cancel"}:
                raise ValueError("Invalid task action")
            task = self.store.get_task(tid)
            if task is None:
                raise KeyError(tid)
            if not isinstance(turn_id, str) or not turn_id:
                raise ValueError("Turn ID required")
            if action["kind"] == "suspend":
                from .workflows import workflow_run_views, TERMINAL
                if any(run["status"] not in TERMINAL for run in workflow_run_views(self.store, tid)):
                    raise TaskConflict("An active workflow can be stopped, but cannot be suspended at an arbitrary node")
            params = {"threadId": task["thread_id"], "turnId": turn_id, "actionId": action_id, "action": action}
            self._execute(tid, action_id, "turn/action", params)
            if action["kind"] == "respond":
                answer = action["answer"]
                text = answer.get("text") if answer["kind"] == "text" else ", ".join(answer.get("selected", []) + answer.get("custom", []))
                self.store.upsert_message(dict(task_id=tid, turn_id=f"{tid}/reply/{action_id}", role="user", content=text, status="COMPLETED"))
            self._start_watching()
            return self.get_task(tid)

    def approve(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Invalid task request")
        self._require_started(payload.get("task_id"))
        tid = required_id(payload.get("task_id"), "task ID")
        task = self.store.get_task(tid)
        if task is None:
            raise KeyError(tid)
        if payload.get("decision") not in {"allow", "deny"}:
            raise ValueError("Invalid decision")
        review = self.store.risk_review(tid, payload["request_id"])
        if review and review["status"] == "reviewing":
            raise TaskConflict("Risk review is still running")
        self.process.start()
        self.process.request("approval/resolve", {"threadId": task["thread_id"], "turnId": payload["turn_id"],
                             "requestId": payload["request_id"], "decision": payload["decision"]})
        self._start_watching()
        return self.get_task(tid)

    def recover_task(self, tid):
        self._require_started(tid)
        with self._lock:
            self._require_started(tid)
            tid = required_id(tid, "task ID")
            task = self.store.get_task(tid)
            if task is None:
                raise KeyError(tid)
            self.process.start()
            self.process.clear_execution_failure(tid)
            self.process.request("thread/resume", {"threadId": task["thread_id"]})
            return self.get_task(tid)

    def workflow_feedback(self, payload):
        from .workflows import resume_workflow
        tid = required_id(payload.get("task_id"), "task ID")
        required_id(payload.get("action_id"), "action ID")
        if self.store.get_task(tid) is None:
            raise KeyError(tid)
        result = resume_workflow(self.store, tid, payload)
        if result["status"] == 409:
            raise TaskConflict(result["message"])
        if result["status"] == 400:
            raise ValueError(result["message"])
        if result["status"] != 200:
            raise TaskAgentError("Workflow continuation was not confirmed")
        return self.get_task(tid)

    def read_tool_result(self, payload):
        tid = required_id(payload.get("task_id"), "task ID")
        task = self.store.get_task(tid)
        if task is None:
            raise KeyError(tid)
        event = next((e for e in self.store.events(tid) if e["id"] == payload.get("event_id")), None)
        if not event or not event.get("result"):
            raise ValueError("Tool result not found")
        self.process.start()
        return self.process.request("thread/toolResult/read", {"threadId": task["thread_id"], "ref": event["result"]["ref"],
                                    "part": payload.get("part", "content"), "offset": payload.get("offset", 0), "limit": 65536})

    def list_skills(self, search: str = "") -> list[dict]:
        return self.skills_library.list(search)

    def local_skills(self) -> dict:
        return self.skills_library.local_skills()

    def get_skill(self, skill_id: str) -> dict:
        return self.skills_library.get(skill_id)

    def save_skill(self, payload: dict) -> dict:
        return self.skills_library.save(payload)

    def import_skill(self, payload: dict) -> dict:
        return self.skills_library.import_path(payload)

    def delete_skill(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("Invalid skill delete payload")
        expected = payload.get("expected_updated_at")
        if expected is not None and not isinstance(expected, str):
            raise ValueError("Invalid expected_updated_at")
        return self.skills_library.delete(payload.get("skill_id"), expected_updated_at=expected)

    def skill_files(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("Invalid skill files payload")
        return self.skills_library.files(payload.get("skill_id"), version=payload.get("version"))

    def skill_preview_file(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("Invalid skill preview payload")
        return self.skills_library.preview(payload.get("skill_id"), payload.get("path"), version=payload.get("version"))

    def open_skill_directory(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("Invalid skill directory request")
        return self.skills_library.open_directory(payload.get("skill_id"), version=payload.get("version"))

    def list_mcp_servers(self, search: str = "") -> list[dict]:
        return self.mcp_library.list(search)

    def get_mcp_server(self, server_id: str) -> dict:
        return self.mcp_library.get(server_id)

    def save_mcp_server(self, payload: dict) -> dict:
        return self.mcp_library.save(payload)

    def delete_mcp_server(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("Invalid MCP server delete payload")
        expected = payload.get("expected_updated_at")
        if expected is not None and not isinstance(expected, str):
            raise ValueError("Invalid expected_updated_at")
        return self.mcp_library.delete(payload.get("server_id"), expected_updated_at=expected)

    def test_mcp_server(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("Invalid MCP server test payload")
        return self.mcp_library.test(payload.get("server_id"))

    def set_mcp_tool_enabled(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("Invalid MCP tool toggle payload")
        expected = payload.get("expected_updated_at")
        if expected is not None and not isinstance(expected, str):
            raise ValueError("Invalid expected_updated_at")
        return self.mcp_library.set_tool_enabled(
            payload.get("server_id"),
            tool_name=payload.get("tool_name"),
            enabled=payload.get("enabled"),
            enabled_tool_names=payload.get("enabled_tool_names"),
            expected_updated_at=expected,
        )

    def list_mcp_tools(self) -> list[dict]:
        from .integrations import public_mcp_tools_catalog
        return public_mcp_tools_catalog(self.task_root, self.store)


_service: TaskAgentService | None = None
_service_lock = threading.Lock()


def task_agent_service() -> TaskAgentService:
    global _service
    with _service_lock:
        if _service is None:
            _service = TaskAgentService(Path.cwd())
        return _service


def stop_task_agent_service() -> None:
    with _service_lock:
        service = _service
    if service is not None:
        service.stop()
