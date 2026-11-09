"""Durable local Agent schedules. Every occurrence owns stable task and turn IDs."""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .client import TaskAgentError
from .config import ConfigError, build_model_snapshot, current_llm_settings
from .permissions import validate_permission_mode
from .projects import ProjectError, validate_saved_roots
from .store import now

TERMINAL = {"COMPLETED", "FAILED", "INTERRUPTED"}


class ScheduleError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _utc(value=None):
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _next(data, instant):
    from utilities.workflow.scheduler import get_next_run_time
    result = get_next_run_time(data["cron_expression"], data["timezone"], instant, recurrence=data["recurrence"])
    return result.astimezone(timezone.utc).isoformat() if result else None


class AgentScheduler:
    def __init__(self, service):
        self.service = service
        self.store = service.store
        self.closed = threading.Event()
        self.wake = threading.Event()
        self.worker = None
        self._tick_lock = threading.Lock()

    def start(self):
        if self.worker is None:
            self.worker = threading.Thread(target=self._loop, daemon=True, name="task-agent-schedules")
            self.worker.start()
            self.service._start_watching()

    def stop(self):
        self.closed.set()
        self.wake.set()
        if self.worker is not None:
            self.worker.join(timeout=2)

    def _loop(self):
        while not self.closed.is_set():
            try:
                self.tick()
            except Exception:
                # A malformed record or temporary database failure must not stop future schedules.
                pass
            self.wake.wait(10)
            self.wake.clear()

    @staticmethod
    def _record(row):
        if row is None:
            raise KeyError("schedule")
        return {"existing_task_id": None, **json.loads(row["data"]), **{key: row[key] for key in
                ("schedule_id", "task_id", "next_run_at", "created_at", "updated_at")}}

    @staticmethod
    def _run_view(row):
        return {key: row[key] for key in ("run_id", "task_id", "status", "error_code", "scheduled_at", "finished_at")} if row else None

    def get(self, sid):
        from .service import required_id
        required_id(sid, "schedule ID")
        with self.store.connect() as db:
            record = self._record(db.execute("SELECT * FROM task_schedules WHERE schedule_id=?", (sid,)).fetchone())
            record["last_run"] = self._run_view(db.execute(
                "SELECT * FROM task_schedule_runs WHERE schedule_id=? ORDER BY scheduled_at DESC,run_id DESC LIMIT 1", (sid,)).fetchone())
            if record["last_run"] and not db.execute("SELECT 1 FROM tasks WHERE tid=?", (record["last_run"]["task_id"],)).fetchone():
                record["last_run"]["task_id"] = None
        return record

    def list(self):
        with self.store.connect() as db:
            ids = [row[0] for row in db.execute("SELECT schedule_id FROM task_schedules ORDER BY created_at DESC,schedule_id")]
        return [self.get(sid) for sid in ids]

    def save(self, payload):
        from .service import required_id, required_text
        from utilities.workflow.scheduler import validate_cron_expression, normalize_recurrence
        sid = required_id(payload.get("schedule_id"), "schedule ID")
        data = {
            "name": payload.get("name", ""), "goal": required_text(payload.get("goal"), "goal"),
            "agent_id": required_id(payload.get("agent_id", "general"), "agent ID"),
            "project_id": payload.get("project_id") or None,
            "run_mode": payload.get("run_mode", "new"),
            "existing_task_id": payload.get("existing_task_id") or None,
            "model_provider": payload.get("model_provider"), "model": payload.get("model"),
            "reasoning_effort": payload.get("reasoning_effort", "default"),
            "permission_mode": validate_permission_mode(payload.get("permission_mode", "auto")),
            "cron_expression": payload.get("cron_expression"), "timezone": payload.get("timezone"),
            "recurrence": normalize_recurrence(payload.get("recurrence")),
        }
        if not isinstance(data["name"], str) or len(data["name"].encode("utf-8")) > 160:
            raise ValueError("Invalid schedule name")
        data["name"] = data["name"].strip() or data["goal"].splitlines()[0][:40]
        if data["run_mode"] not in {"new", "continue"}:
            raise ValueError("Invalid run mode")
        target = None
        if data["existing_task_id"] is not None:
            if data["run_mode"] != "continue":
                raise ValueError("An existing task requires continuation mode")
            target = self.store.get_task(required_id(data["existing_task_id"], "task ID"))
            if target is None:
                raise ScheduleError("task_missing")
            target_agent = target["config_snapshot"].get("agent_profile", {}).get("agent_id", "general")
            if data["project_id"] != target["project_id"] or data["agent_id"] != target_agent:
                raise ScheduleError("changed")
        for key, default in (("hide_after_run", False), ("notify_after_run", True), ("enabled", True)):
            data[key] = payload.get(key, default)
            if type(data[key]) is not bool:
                raise ValueError("Invalid schedule switch")
        if not isinstance(data["timezone"], str) or not data["timezone"]:
            raise ValueError("Invalid timezone")
        try:
            ZoneInfo(data["timezone"])
        except ZoneInfoNotFoundError:
            raise ValueError("Invalid timezone") from None
        if not isinstance(data["cron_expression"], str) or not validate_cron_expression(data["cron_expression"]):
            raise ValueError("Invalid schedule pattern")
        data["cron_expression"] = data["cron_expression"].strip()
        self.service.get_profile(data["agent_id"])
        if data["project_id"] is not None:
            project = self.service.get_project(required_id(data["project_id"], "project ID"))
            if data["enabled"] and any(not folder["available"] for folder in project["folders"]):
                raise ScheduleError("project_unavailable")
        if data["enabled"]:
            settings = current_llm_settings()
            model = build_model_snapshot(settings, data["model_provider"], data["model"], data["reasoning_effort"])
            if settings["backends"][model["backend"]]["models"][model["requested_model"]].get("enabled") is False:
                raise ConfigError("Selected model is disabled")
        else:
            required_text(data["model_provider"], "model provider", 160)
            required_text(data["model"], "model", 160)
        timestamp = now()
        next_run = _next(data, datetime.fromisoformat(timestamp)) if data["enabled"] else None
        if data["enabled"] and next_run is None:
            raise ScheduleError("config_invalid")
        with self.service._lock, self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if data["existing_task_id"] and not db.execute("SELECT 1 FROM tasks WHERE tid=?", (data["existing_task_id"],)).fetchone():
                raise ScheduleError("task_missing")
            previous = db.execute("SELECT * FROM task_schedules WHERE schedule_id=?", (sid,)).fetchone()
            if previous:
                if payload.get("expected_updated_at") != previous["updated_at"]:
                    raise ScheduleError("changed")
                old = self._record(previous)
                same_binding = old["run_mode"] == data["run_mode"] and old["existing_task_id"] == data["existing_task_id"]
                if old["task_id"] and data["run_mode"] == "continue" and same_binding and any(data[key] != old[key] for key in ("project_id", "agent_id")):
                    raise ScheduleError("changed")
                task_id = data["existing_task_id"] or (old["task_id"] if same_binding else None)
                db.execute("UPDATE task_schedules SET data=?,task_id=?,next_run_at=?,updated_at=? WHERE schedule_id=?",
                           (json.dumps(data), task_id, next_run, timestamp, sid))
            else:
                if payload.get("expected_updated_at") is not None:
                    raise ScheduleError("changed")
                db.execute("INSERT INTO task_schedules VALUES(?,?,?,?,?,?)", (sid, json.dumps(data), data["existing_task_id"], next_run, timestamp, timestamp))
        self.wake.set()
        return self.get(sid)

    def delete(self, payload):
        from .service import required_id
        sid = required_id(payload.get("schedule_id"), "schedule ID")
        with self.service._lock, self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM task_schedules WHERE schedule_id=?", (sid,)).fetchone()
            if row is None:
                raise KeyError(sid)
            if payload.get("expected_updated_at") != row["updated_at"]:
                raise ScheduleError("changed")
            db.execute("DELETE FROM task_schedules WHERE schedule_id=?", (sid,))
        return {"deleted": True}

    def run_now(self, payload):
        from .service import required_id
        sid = required_id(payload.get("schedule_id"), "schedule ID")
        request_id = required_id(payload.get("input_id"), "run ID")
        run = self._admit(sid, _utc(), manual_id=request_id)
        self.wake.set()
        return self._run_view(run)

    def retry_run(self, payload):
        from .service import required_id
        sid = required_id(payload.get("schedule_id"), "schedule ID")
        rid = required_id(payload.get("run_id"), "run ID")
        with self.service._lock, self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            run = db.execute("SELECT * FROM task_schedule_runs WHERE schedule_id=? AND run_id=?", (sid, rid)).fetchone()
            if run is None:
                raise KeyError(rid)
            if run["status"] == "UNKNOWN":
                db.execute("UPDATE task_schedule_runs SET status='ADMITTED',error_code=NULL,finished_at=NULL WHERE run_id=?", (rid,))
            result = self._run_view(db.execute("SELECT * FROM task_schedule_runs WHERE run_id=?", (rid,)).fetchone())
        self.wake.set()
        return result

    def _admit(self, sid, instant, *, manual_id=None):
        slot = f"manual:{manual_id}" if manual_id else instant.replace(second=0, microsecond=0).isoformat()
        run_id = "sched_" + hashlib.sha256(f"{sid}:{slot}".encode()).hexdigest()[:40]
        with self.service._lock, self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT * FROM task_schedule_runs WHERE run_id=?", (run_id,)).fetchone()
            if previous:
                return dict(previous)
            schedule = self._record(db.execute("SELECT * FROM task_schedules WHERE schedule_id=?", (sid,)).fetchone())
            if not schedule["enabled"]:
                raise ScheduleError("disabled")
            if not manual_id:
                if not schedule["next_run_at"] or datetime.fromisoformat(schedule["next_run_at"]) > instant:
                    return None
                # Do not replay a backlog when the app was closed.
                db.execute("UPDATE task_schedules SET next_run_at=? WHERE schedule_id=?", (_next(schedule, instant), sid))
            task_id = schedule["task_id"] if schedule["run_mode"] == "continue" else None
            task_id = task_id or f"task_{run_id}"
            task = db.execute("SELECT * FROM tasks WHERE tid=?", (task_id,)).fetchone()
            unresolved = db.execute("SELECT 1 FROM task_schedule_runs WHERE schedule_id=? AND status IN ('ADMITTED','UNKNOWN') LIMIT 1", (sid,)).fetchone()
            if unresolved and not manual_id:
                return None
            error = "busy" if unresolved or (task and task["status"] not in TERMINAL) else None
            if not manual_id and datetime.fromisoformat(schedule["next_run_at"]) < instant.replace(second=0, microsecond=0):
                error = "missed"
            if schedule["task_id"] and schedule["run_mode"] == "continue" and task is None:
                error = "task_missing"
            if manual_id and error:
                raise ScheduleError(error)
            status = "SKIPPED" if error else "ADMITTED"
            request = {key: value for key, value in schedule.items() if key not in {"last_run", "created_at", "updated_at", "next_run_at", "task_id"}}
            request["existing_task"] = bool(task)
            request["expected_turn_id"] = task["current_turn_id"] if task else None
            request["expected_revision"] = (json.loads(task["config_snapshot"]).get("runtime_settings") or {}).get("revision", 0) if task else 0
            db.execute("INSERT INTO task_schedule_runs VALUES(?,?,?,?,?,?,?,?,?)", (
                run_id, sid, task_id, f"{task_id}/turn/{run_id}", status, error,
                instant.isoformat(), instant.isoformat() if error else None, json.dumps(request)))
            if not error and schedule["run_mode"] == "continue":
                db.execute("UPDATE task_schedules SET task_id=? WHERE schedule_id=?", (task_id, sid))
            return dict(db.execute("SELECT * FROM task_schedule_runs WHERE run_id=?", (run_id,)).fetchone())

    def tick(self, instant=None):
        if not self._tick_lock.acquire(blocking=False):
            return
        try:
            instant = _utc(instant)
            with self.store.connect() as db:
                due = [row[0] for row in db.execute("SELECT schedule_id FROM task_schedules WHERE next_run_at IS NOT NULL AND next_run_at<=?", (instant.isoformat(),))]
            for sid in due:
                if self.closed.is_set():
                    return
                try:
                    self._admit(sid, instant)
                except (KeyError, ValueError):
                    continue
            with self.store.connect() as db:
                admitted = [dict(row) for row in db.execute("SELECT * FROM task_schedule_runs WHERE status='ADMITTED' ORDER BY scheduled_at")]
            for run in admitted:
                if self.closed.is_set():
                    return
                self._dispatch(run)
        finally:
            self._tick_lock.release()

    def _dispatch(self, run):
        from .service import TaskConflict
        data = json.loads(run["data"])
        tid, rid = run["task_id"], run["run_id"]
        try:
            with self.service._lock:
                if data["existing_task"]:
                    task = self.store.get_task(tid)
                    if not task:
                        raise ScheduleError("task_missing")
                    existing = self.store.command(tid, rid)
                    if not existing:
                        detail = self.service.get_task(tid)
                        task = detail["task"]
                        if detail["sync_error"]:
                            raise TaskAgentError("Unavailable")
                        unconfirmed = (detail.get("state") or {}).get("unconfirmedCount", 0) > 0 and not detail.get("model_rejection_only")
                        if task["status"] not in TERMINAL or task["current_turn_id"] != data["expected_turn_id"] or unconfirmed:
                            raise ScheduleError("busy")
                        if data["project_id"]:
                            validate_saved_roots(task["config_snapshot"]["project"]["roots"])
                        self.service.update_runtime_settings({"task_id": tid, "request_id": f"model_{rid}",
                            "expected_revision": data["expected_revision"], **{key: data[key] for key in
                            ("model_provider", "model", "reasoning_effort", "permission_mode")}})
                    if not existing:
                        self.store.update_task(tid, hidden=0)
                    result = self.service.send_message({"task_id": tid, "input_id": rid, "text": data["goal"]})
                else:
                    result = self.service.create_task({"input_id": tid, "turn_input_id": rid, **{key: data[key] for key in
                        ("goal", "agent_id", "project_id", "model_provider", "model", "reasoning_effort", "permission_mode")}})
                task = result["task"]
                with self.store.connect() as db:
                    db.execute("UPDATE task_schedule_runs SET status='RUNNING' WHERE run_id=? AND status='ADMITTED'", (rid,))
                if task["status"] in TERMINAL and not result.get("sync_error"):
                    self.complete_task(tid, task["current_turn_id"], task["status"])
        except (ConfigError, ProjectError, ScheduleError, TaskConflict, ValueError, KeyError) as error:
            code = error.code if isinstance(error, ScheduleError) else "project_unavailable" if isinstance(error, ProjectError) else "config_invalid"
            self._fail_run(rid, "SKIPPED" if code == "busy" else "FAILED", code)
        except Exception:
            # Existing command receipts and stable input IDs let the task's retry UI reconcile an uncertain dispatch.
            self._fail_run(rid, "UNKNOWN", "connection_unavailable")

    def _fail_run(self, rid, status, code):
        with self.store.connect() as db:
            changed = db.execute("UPDATE task_schedule_runs SET status=?,error_code=?,finished_at=? WHERE run_id=? AND status IN ('ADMITTED','RUNNING')", (status, code, now(), rid)).rowcount
            run = db.execute("SELECT data FROM task_schedule_runs WHERE run_id=?", (rid,)).fetchone()
        if changed and status == "FAILED" and run and json.loads(run["data"])["notify_after_run"]:
            from utilities.desktop_notifications import notify_task_finished
            notify_task_finished("FAILED")

    def complete_task(self, tid, turn_id, status):
        if status not in TERMINAL or not turn_id:
            return
        notify = True
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            run = db.execute("SELECT * FROM task_schedule_runs WHERE task_id=? AND turn_id=? LIMIT 1", (tid, turn_id)).fetchone()
            if run:
                data = json.loads(run["data"])
                notify = data["notify_after_run"]
                db.execute("UPDATE task_schedule_runs SET status=?,error_code=NULL,finished_at=? WHERE run_id=? AND status IN ('ADMITTED','RUNNING','UNKNOWN')", (status, now(), run["run_id"]))
            claimed = db.execute("INSERT OR IGNORE INTO task_completion_effects VALUES(?,?,?)", (tid, turn_id, now())).rowcount
            if not claimed:
                return
            if run and data["hide_after_run"]:
                db.execute("UPDATE tasks SET hidden=1 WHERE tid=? AND current_turn_id=? AND status IN ('COMPLETED','FAILED','INTERRUPTED')", (tid, turn_id))
        if notify:
            from utilities.desktop_notifications import notify_task_finished
            notify_task_finished(status)
