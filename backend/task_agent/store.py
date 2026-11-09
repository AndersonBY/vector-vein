"""Versioned desktop-owned task and message projection."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 10


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BusinessStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if not 0 <= version <= SCHEMA_VERSION:
                raise ValueError("Unsupported task database schema")
            if version == 0:
                connection.executescript(
                    """
                    CREATE TABLE tasks (
                        tid TEXT PRIMARY KEY,
                        thread_id TEXT NOT NULL UNIQUE,
                        title TEXT NOT NULL,
                        goal TEXT NOT NULL,
                        status TEXT NOT NULL,
                        current_turn_id TEXT,
                        model_provider TEXT NOT NULL,
                        model TEXT NOT NULL,
                        reasoning_effort TEXT NOT NULL,
                        config_snapshot TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE messages (
                        mid TEXT PRIMARY KEY,
                        task_id TEXT NOT NULL REFERENCES tasks(tid) ON DELETE CASCADE,
                        turn_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        status TEXT NOT NULL,
                        attachments TEXT NOT NULL DEFAULT '[]',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(task_id, turn_id, role)
                    );
                    CREATE INDEX messages_task_order ON messages(task_id, created_at, mid);
                    PRAGMA user_version=1;
                    """
                )

            if version < 2:
                connection.executescript("""
                    CREATE TABLE task_projection (
                        task_id TEXT PRIMARY KEY REFERENCES tasks(tid), cursor TEXT, state TEXT NOT NULL DEFAULT '{}'
                    );
                    CREATE TABLE task_events (
                        task_id TEXT NOT NULL REFERENCES tasks(tid), event_id TEXT NOT NULL,
                        seq INTEGER NOT NULL, ordinal INTEGER NOT NULL, data TEXT NOT NULL,
                        PRIMARY KEY(task_id, event_id)
                    );
                    CREATE TABLE task_commands (
                        task_id TEXT NOT NULL REFERENCES tasks(tid), command_id TEXT NOT NULL,
                        method TEXT NOT NULL, params TEXT NOT NULL, receipt TEXT,
                        PRIMARY KEY(task_id, command_id)
                    );
                    CREATE TABLE task_agent_profiles (
                        agent_id TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL
                    );
                    PRAGMA user_version=2;
                """)

            if version < 3:
                connection.executescript("""
                    CREATE TABLE task_workflow_jobs (
                        job_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(tid),
                        run_id TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, result TEXT
                    );
                    CREATE INDEX task_workflow_jobs_task ON task_workflow_jobs(task_id);
                    PRAGMA user_version=3;
                """)

            if version < 4:
                connection.executescript("""
                    CREATE TABLE task_model_failures (
                        task_id TEXT NOT NULL REFERENCES tasks(tid), call_id TEXT NOT NULL, data TEXT NOT NULL,
                        PRIMARY KEY(task_id, call_id)
                    );
                    PRAGMA user_version=4;
                """)

            if version < 5:
                connection.executescript("""
                    CREATE TABLE task_risk_reviews (
                        task_id TEXT NOT NULL REFERENCES tasks(tid), request_id TEXT NOT NULL,
                        fingerprint TEXT NOT NULL, data TEXT NOT NULL,
                        PRIMARY KEY(task_id, request_id)
                    );
                    PRAGMA user_version=5;
                """)

            if version < 6:
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute("PRAGMA user_version").fetchone()[0] < 6:
                    connection.execute("""CREATE TABLE task_projects (
                        project_id TEXT PRIMARY KEY, name TEXT NOT NULL, roots TEXT NOT NULL,
                        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
                    connection.execute("ALTER TABLE tasks ADD COLUMN project_id TEXT REFERENCES task_projects(project_id)")
                    connection.execute("CREATE INDEX tasks_project_order ON tasks(project_id, updated_at DESC)")
                    connection.execute("PRAGMA user_version=6")

            if version < 7:
                if not connection.in_transaction:
                    connection.execute("BEGIN IMMEDIATE")
                if connection.execute("PRAGMA user_version").fetchone()[0] < 7:
                    connection.execute("""CREATE TABLE IF NOT EXISTS task_skills (
                        skill_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL,
                        enabled INTEGER NOT NULL DEFAULT 1,
                        version INTEGER NOT NULL,
                        data TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )""")
                    connection.execute("""CREATE TABLE IF NOT EXISTS task_skill_revisions (
                        skill_id TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        bundle_path TEXT NOT NULL,
                        data TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        PRIMARY KEY(skill_id, version)
                    )""")
                    connection.execute("CREATE INDEX IF NOT EXISTS task_skills_order ON task_skills(updated_at DESC, skill_id ASC)")
                    connection.execute("PRAGMA user_version=7")

            if version < 8:
                if not connection.in_transaction:
                    connection.execute("BEGIN IMMEDIATE")
                if connection.execute("PRAGMA user_version").fetchone()[0] < 8:
                    connection.execute("""CREATE TABLE IF NOT EXISTS task_mcp_servers (
                        server_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL,
                        transport TEXT NOT NULL,
                        enabled INTEGER NOT NULL DEFAULT 1,
                        config TEXT NOT NULL,
                        secrets TEXT NOT NULL DEFAULT '{}',
                        tools TEXT NOT NULL DEFAULT '[]',
                        status TEXT NOT NULL DEFAULT '{}',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )""")
                    connection.execute("CREATE INDEX IF NOT EXISTS task_mcp_servers_order ON task_mcp_servers(updated_at DESC, server_id ASC)")
                    connection.execute("PRAGMA user_version=8")

            if version < 9:
                if not connection.in_transaction:
                    connection.execute("BEGIN IMMEDIATE")
                if connection.execute("PRAGMA user_version").fetchone()[0] < 9:
                    connection.execute("""CREATE TABLE IF NOT EXISTS task_mcp_jobs (
                        job_id TEXT PRIMARY KEY,
                        task_id TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        server_id TEXT NOT NULL,
                        tool_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        result TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )""")
                    connection.execute("CREATE INDEX IF NOT EXISTS task_mcp_jobs_task_order ON task_mcp_jobs(task_id, created_at, job_id)")
                    connection.execute("PRAGMA user_version=9")

            if version < 10:
                if not connection.in_transaction:
                    connection.execute("BEGIN IMMEDIATE")
                if connection.execute("PRAGMA user_version").fetchone()[0] < 10:
                    connection.execute("ALTER TABLE tasks ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0")
                    connection.execute("""CREATE TABLE task_schedules (
                        schedule_id TEXT PRIMARY KEY, data TEXT NOT NULL,
                        task_id TEXT, next_run_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
                    connection.execute("""CREATE TABLE task_schedule_runs (
                        run_id TEXT PRIMARY KEY, schedule_id TEXT NOT NULL, task_id TEXT NOT NULL,
                        turn_id TEXT NOT NULL, status TEXT NOT NULL, error_code TEXT,
                        scheduled_at TEXT NOT NULL, finished_at TEXT, data TEXT NOT NULL)""")
                    connection.execute("CREATE INDEX task_schedule_runs_schedule ON task_schedule_runs(schedule_id, scheduled_at DESC)")
                    connection.execute("CREATE INDEX task_schedule_runs_task ON task_schedule_runs(task_id, turn_id)")
                    connection.execute("""CREATE TABLE task_completion_effects (
                        task_id TEXT NOT NULL, turn_id TEXT NOT NULL, created_at TEXT NOT NULL,
                        PRIMARY KEY(task_id, turn_id))""")
                    connection.execute("PRAGMA user_version=10")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _task(row) -> dict:
        result = dict(row)
        result["config_snapshot"] = json.loads(result["config_snapshot"])
        return result

    @staticmethod
    def _message(row) -> dict:
        result = dict(row)
        result["attachments"] = json.loads(result["attachments"])
        return result

    def get_task(self, tid: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE tid=?", (tid,)).fetchone()
        return self._task(row) if row else None

    def list_tasks(self, limit: int = 20, project_id: str | None = None, offset: int = 0, search: str = "") -> list[dict]:
        return self.query_tasks(limit, project_id, offset, search)["tasks"]

    def query_tasks(self, limit=20, project_id=None, offset=0, search="", *, statuses=(), agent_id=None,
                    sort_by="updated_at", sort_order="desc", summary=False, visibility="visible"):
        if sort_by not in {"created_at", "updated_at"} or sort_order not in {"asc", "desc"}:
            raise ValueError("Invalid task sort")
        if visibility not in {"visible", "hidden", "all"}:
            raise ValueError("Invalid task visibility")
        filters, params = [], []
        if visibility != "all":
            filters.append("hidden=?")
            params.append(int(visibility == "hidden"))
        if project_id:
            filters.append("project_id=?")
            params.append(project_id)
        if search.strip():
            filters.append("(instr(lower(title), lower(?))>0 OR instr(lower(goal), lower(?))>0)")
            params.extend([search.strip(), search.strip()])
        if statuses:
            filters.append("status IN (" + ",".join("?" for _ in statuses) + ")")
            params.extend(statuses)
        if agent_id:
            filters.append("coalesce(json_extract(config_snapshot, '$.agent_profile.agent_id'), 'general')=?")
            params.append(agent_id)
        where = " WHERE " + " AND ".join(filters) if filters else ""
        with self.connect() as connection:
            # Sidebar polling does not need event aggregates or catalog-wide counts.
            select = "tasks.*"
            if summary:
                select += """, coalesce((SELECT max(json_extract(e.data, '$.cycle')) FROM task_events e
                    WHERE e.task_id=tasks.tid AND json_type(e.data, '$.cycle') IN ('integer','real')), 0) AS current_cycle_index"""
            rows = connection.execute(f"SELECT {select} FROM tasks" + where + f" ORDER BY {sort_by} {sort_order}, tid {sort_order} LIMIT ? OFFSET ?",
                                      (*params, limit, offset)).fetchall()
            result = {"tasks": [self._task(row) for row in rows]}
            if summary:
                result["total"] = connection.execute("SELECT count(*) FROM tasks" + where, params).fetchone()[0]
                scope = " WHERE project_id=?" if project_id else ""
                agents = connection.execute("""SELECT coalesce(json_extract(config_snapshot, '$.agent_profile.agent_id'), 'general') AS agent_id,
                    coalesce(json_extract(config_snapshot, '$.agent_profile.name'), '') AS name FROM tasks"""
                    + scope + " ORDER BY updated_at DESC, tid DESC", (project_id,) if project_id else ()).fetchall()
                result["agents"] = list({agent["agent_id"]: dict(agent) for agent in reversed(agents)}.values())
        return result

    def create_task(self, task: dict, first_message: dict | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO tasks(tid,thread_id,title,goal,status,current_turn_id,model_provider,model,
                   reasoning_effort,config_snapshot,created_at,updated_at,project_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    task["tid"], task["thread_id"], task["title"], task["goal"], task["status"], task["current_turn_id"],
                    task["model_provider"], task["model"], task["reasoning_effort"], json.dumps(task["config_snapshot"]),
                    task["created_at"], task["updated_at"], task.get("project_id"),
                ),
            )

            if first_message is not None:
                self._upsert_message(connection, first_message)

    def update_task(self, tid: str, **fields) -> None:
        if not fields:
            return
        current = self.get_task(tid)
        if current and all(current.get(key) == value for key, value in fields.items()):
            return
        fields["updated_at"] = now()
        columns = ", ".join(f"{key}=?" for key in fields)
        with self.connect() as connection:
            connection.execute(f"UPDATE tasks SET {columns} WHERE tid=?", (*fields.values(), tid))

    def upsert_message(self, message: dict) -> None:
        with self.connect() as connection:
            self._upsert_message(connection, message)

    @staticmethod
    def _upsert_message(connection, message: dict) -> None:
        timestamp = now()
        connection.execute(
            """INSERT INTO messages(mid,task_id,turn_id,role,content,status,attachments,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(task_id,turn_id,role) DO UPDATE SET
               content=excluded.content,status=excluded.status,attachments=excluded.attachments,updated_at=excluded.updated_at""",
            (
                message.get("mid", uuid.uuid4().hex), message["task_id"], message["turn_id"], message["role"],
                message["content"], message["status"], json.dumps(message.get("attachments", [])),
                message.get("created_at", timestamp), timestamp,
            ),
        )

    def list_messages(self, tid: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM messages WHERE task_id=? ORDER BY created_at,mid", (tid,)).fetchall()
        return [self._message(row) for row in rows]

    def projection(self, tid: str) -> dict:
        with self.connect() as connection:
            row = connection.execute("SELECT cursor,state FROM task_projection WHERE task_id=?", (tid,)).fetchone()
        return {"cursor": json.loads(row["cursor"]) if row["cursor"] else None, "state": json.loads(row["state"])} if row else {"cursor": None, "state": {}}

    def save_event_page(self, tid: str, page: dict) -> None:
        from .projection import project_event
        with self.connect() as connection:
            for entry in page["events"]:
                event = project_event(entry["event"])
                if event is not None:
                    connection.execute("INSERT OR IGNORE INTO task_events VALUES(?,?,?,?,?)", (
                        tid, event["id"], entry["cursor"]["seq"], entry["cursor"]["offset"], json.dumps(event, ensure_ascii=False),
                    ))
            connection.execute("""INSERT INTO task_projection(task_id,cursor) VALUES(?,?)
                ON CONFLICT(task_id) DO UPDATE SET cursor=excluded.cursor""", (tid, json.dumps(page["nextCursor"])))

    def save_state(self, tid: str, state: dict) -> None:
        with self.connect() as connection:
            connection.execute("""INSERT INTO task_projection(task_id,state) VALUES(?,?)
                ON CONFLICT(task_id) DO UPDATE SET state=excluded.state""", (tid, json.dumps(state, ensure_ascii=False)))

    def events(self, tid: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute("SELECT data FROM task_events WHERE task_id=? ORDER BY seq,ordinal", (tid,)).fetchall()
        return [json.loads(row["data"]) for row in rows]

    def command(self, tid: str, command_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM task_commands WHERE task_id=? AND command_id=?", (tid, command_id)).fetchone()
        return {**dict(row), "params": json.loads(row["params"]), "receipt": json.loads(row["receipt"]) if row["receipt"] else None} if row else None

    def save_command(self, tid: str, command_id: str, method: str, params: dict) -> None:
        with self.connect() as connection:
            connection.execute("INSERT OR IGNORE INTO task_commands VALUES(?,?,?,?,NULL)", (tid, command_id, method, json.dumps(params)))

    def complete_command(self, tid: str, command_id: str, receipt: dict) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE task_commands SET receipt=? WHERE task_id=? AND command_id=?", (json.dumps(receipt), tid, command_id))

    def profiles(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute("SELECT data, updated_at FROM task_agent_profiles ORDER BY updated_at DESC").fetchall()
        return [{**json.loads(row["data"]), "updated_at": row["updated_at"]} for row in rows]

    def get_profile(self, agent_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute("SELECT data, updated_at FROM task_agent_profiles WHERE agent_id=?", (agent_id,)).fetchone()
        return {**json.loads(row["data"]), "updated_at": row["updated_at"]} if row else None

    def save_profile(self, profile: dict) -> None:
        with self.connect() as connection:
            connection.execute("INSERT INTO task_agent_profiles VALUES(?,?,?) ON CONFLICT(agent_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at",
                               (profile["agent_id"], json.dumps(profile, ensure_ascii=False), profile.get("updated_at") or now()))

    def watched_tasks(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute("""SELECT tasks.* FROM tasks LEFT JOIN task_projection p ON p.task_id=tasks.tid
                WHERE tasks.status IN ('PENDING','PROCESSING','WAITING_FOR_USER','WAITING_FOR_APPROVAL','WAITING_FOR_WORKFLOW','PAUSED')
                   OR json_extract(p.state, '$.history_pending')=1
                ORDER BY tasks.updated_at DESC""").fetchall()
        return [self._task(row) for row in rows]

    def workflow_job(self, job_id):
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM task_workflow_jobs WHERE job_id=?", (job_id,)).fetchone()
        return {**dict(row), "payload": json.loads(row["payload"]), "result": json.loads(row["result"]) if row["result"] else None} if row else None

    def add_workflow_job(self, task_id, job_id, run_id, payload):
        with self.connect() as connection:
            connection.execute("INSERT OR IGNORE INTO task_workflow_jobs VALUES(?,?,?,?,NULL)", (job_id, task_id, run_id, json.dumps(payload, ensure_ascii=False)))
        return self.workflow_job(job_id)

    def finish_workflow_job(self, job_id, result):
        with self.connect() as connection:
            connection.execute("UPDATE task_workflow_jobs SET result=? WHERE job_id=? AND result IS NULL", (json.dumps(result, ensure_ascii=False), job_id))
        return self.workflow_job(job_id)["result"]

    def workflow_jobs(self, task_id):
        with self.connect() as connection:
            rows = connection.execute("SELECT job_id FROM task_workflow_jobs WHERE task_id=? ORDER BY rowid", (task_id,)).fetchall()
        return [self.workflow_job(row["job_id"]) for row in rows]

    def mark_workflow_dispatch_uncertain(self, job_id):
        with self.connect() as connection:
            connection.execute("UPDATE task_workflow_jobs SET payload=json_set(payload, '$.dispatch_uncertain', 1) WHERE job_id=?", (job_id,))

    @staticmethod
    def _mcp_job(row) -> dict | None:
        if not row:
            return None
        return {
            **dict(row),
            "payload": json.loads(row["payload"]),
            "result": json.loads(row["result"]) if row["result"] else None,
        }

    def mcp_job(self, job_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM task_mcp_jobs WHERE job_id=?", (job_id,)).fetchone()
        return self._mcp_job(row)

    def admit_mcp_job(self, task_id: str, session_id: str, job_id: str, server_id: str, tool_name: str, payload: dict) -> tuple[dict, bool]:
        timestamp = now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "INSERT OR IGNORE INTO task_mcp_jobs(job_id, task_id, session_id, server_id, tool_name, status, payload, result, created_at, updated_at) VALUES(?,?,?,?,?,'ADMITTED',?,NULL,?,?)",
                (job_id, task_id, session_id, server_id, tool_name, json.dumps(payload, ensure_ascii=False), timestamp, timestamp),
            )
            inserted = cursor.rowcount == 1
            row = connection.execute("SELECT * FROM task_mcp_jobs WHERE job_id=?", (job_id,)).fetchone()
        return self._mcp_job(row), inserted

    def mark_mcp_job_dispatched(self, job_id: str) -> bool:
        timestamp = now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE task_mcp_jobs SET status='DISPATCHING', payload=json_set(payload, '$.dispatched', 1, '$.dispatched_at', ?), updated_at=? WHERE job_id=? AND status='ADMITTED' AND result IS NULL",
                (timestamp, timestamp, job_id),
            )
            return cursor.rowcount == 1

    def finish_mcp_job(self, job_id: str, status: str, result: dict, *, payload_updates: dict | None = None) -> dict:
        timestamp = now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM task_mcp_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is not None and row["result"] is None:
                payload = json.loads(row["payload"])
                if payload_updates:
                    payload.update(payload_updates)
                connection.execute(
                    "UPDATE task_mcp_jobs SET status=?, payload=?, result=?, updated_at=? WHERE job_id=? AND result IS NULL",
                    (status, json.dumps(payload, ensure_ascii=False), json.dumps(result, ensure_ascii=False), timestamp, job_id),
                )
                row = connection.execute("SELECT * FROM task_mcp_jobs WHERE job_id=?", (job_id,)).fetchone()
        return self._mcp_job(row)["result"]

    def mark_mcp_job_unknown(self, job_id: str, reason: str, *, code: str = "outcome_unknown") -> dict | None:
        timestamp = now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM task_mcp_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                return None
            if row["result"] is not None:
                return self._mcp_job(row)
            payload = json.loads(row["payload"])
            payload.update(dispatch_uncertain=True, unknown_reason=reason, unknown_code=code, unknown_at=timestamp)
            connection.execute(
                "UPDATE task_mcp_jobs SET status='UNKNOWN', payload=?, updated_at=? WHERE job_id=? AND result IS NULL",
                (json.dumps(payload, ensure_ascii=False), timestamp, job_id),
            )
            row = connection.execute("SELECT * FROM task_mcp_jobs WHERE job_id=?", (job_id,)).fetchone()
        return self._mcp_job(row)

    def mcp_jobs(self, task_id: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM task_mcp_jobs WHERE task_id=? ORDER BY created_at, job_id", (task_id,)).fetchall()
        return [self._mcp_job(row) for row in rows]

    def cancel_admitted_mcp_job(self, job_id: str, result: dict) -> bool:
        timestamp = now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM task_mcp_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None or row["status"] != "ADMITTED" or row["result"] is not None:
                return False
            payload = json.loads(row["payload"])
            if payload.get("dispatched"):
                return False
            payload["cancelled_before_dispatch"] = True
            cursor = connection.execute(
                "UPDATE task_mcp_jobs SET status='CANCELLED', payload=?, result=?, updated_at=? WHERE job_id=? AND status='ADMITTED' AND result IS NULL",
                (json.dumps(payload, ensure_ascii=False), json.dumps(result, ensure_ascii=False), timestamp, job_id),
            )
            return cursor.rowcount == 1

    def save_model_failure(self, task_id, call_id, failure):
        if not isinstance(call_id, str) or not call_id:
            return
        with self.connect() as connection:
            connection.execute("INSERT OR REPLACE INTO task_model_failures VALUES(?,?,?)", (task_id, call_id, json.dumps(failure)))

    def model_failures(self, task_id):
        with self.connect() as connection:
            rows = connection.execute("SELECT call_id,data FROM task_model_failures WHERE task_id=?", (task_id,)).fetchall()
        return {row["call_id"]: json.loads(row["data"]) for row in rows}

    def risk_review(self, tid, request_id):
        with self.connect() as connection:
            row = connection.execute("SELECT fingerprint,data FROM task_risk_reviews WHERE task_id=? AND request_id=?", (tid, request_id)).fetchone()
        return {"fingerprint": row["fingerprint"], **json.loads(row["data"])} if row else None

    def start_risk_review(self, tid, request_id, fingerprint, data):
        with self.connect() as connection:
            result = connection.execute("INSERT OR IGNORE INTO task_risk_reviews VALUES(?,?,?,?)", (tid, request_id, fingerprint, json.dumps(data)))
            return result.rowcount == 1

    def finish_risk_review(self, tid, request_id, data):
        with self.connect() as connection:
            connection.execute("UPDATE task_risk_reviews SET data=? WHERE task_id=? AND request_id=? AND json_extract(data, '$.status')='reviewing'", (json.dumps(data), tid, request_id))
        return self.risk_review(tid, request_id)

    def risk_reviews(self, tid):
        with self.connect() as connection:
            rows = connection.execute("SELECT request_id,data FROM task_risk_reviews WHERE task_id=? ORDER BY rowid", (tid,)).fetchall()
        return [{"request_id": row["request_id"], **json.loads(row["data"])} for row in rows]

    @staticmethod
    def _project(row):
        return {**dict(row), "roots": json.loads(row["roots"])} if row else None

    def get_project(self, project_id):
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM task_projects WHERE project_id=?", (project_id,)).fetchone()
        return self._project(row)

    def list_projects(self):
        with self.connect() as connection:
            rows = connection.execute("""SELECT p.*, (SELECT COUNT(*) FROM tasks t WHERE t.project_id=p.project_id) AS task_count
                FROM task_projects p ORDER BY p.updated_at DESC""").fetchall()
        return [self._project(row) for row in rows]

    def save_project(self, project, expected_updated_at=None):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT * FROM task_projects WHERE project_id=?", (project["project_id"],)).fetchone()
            if existing:
                if existing["name"] == project["name"] and json.loads(existing["roots"]) == project["roots"]:
                    return self._project(existing)
                if expected_updated_at != existing["updated_at"]:
                    from .service import TaskConflict
                    raise TaskConflict("The project changed. Refresh before saving.")
                connection.execute("UPDATE task_projects SET name=?,roots=?,updated_at=? WHERE project_id=?",
                                   (project["name"], json.dumps(project["roots"]), now(), project["project_id"]))
            else:
                if expected_updated_at is not None:
                    raise KeyError(project["project_id"])
                timestamp = now()
                connection.execute("INSERT INTO task_projects VALUES(?,?,?,?,?)",
                                   (project["project_id"], project["name"], json.dumps(project["roots"]), timestamp, timestamp))
            return self._project(connection.execute("SELECT * FROM task_projects WHERE project_id=?", (project["project_id"],)).fetchone())

    @staticmethod
    def _skill(row):
        if not row:
            return None
        data = json.loads(row["data"])
        return {
            **data,
            "skill_id": row["skill_id"],
            "name": row["name"],
            "description": row["description"],
            "enabled": bool(row["enabled"]),
            "version": row["version"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_skill(self, skill_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM task_skills WHERE skill_id=?", (skill_id,)).fetchone()
        return self._skill(row)

    def get_skill_revision(self, skill_id: str, version: int) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM task_skill_revisions WHERE skill_id=? AND version=?",
                (skill_id, version),
            ).fetchone()
        if not row:
            return None
        return {
            **json.loads(row["data"]),
            "skill_id": row["skill_id"],
            "version": row["version"],
            "bundle_path": row["bundle_path"],
            "created_at": row["created_at"],
        }

    def list_skills(self, search: str = "") -> list[dict]:
        filters, params = [], []
        if search.strip():
            query = search.strip()
            filters.append("(instr(lower(name), lower(?))>0 OR instr(lower(description), lower(?))>0 OR instr(lower(skill_id), lower(?))>0)")
            params.extend([query, query, query])
        where = " WHERE " + " AND ".join(filters) if filters else ""
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM task_skills" + where + " ORDER BY updated_at DESC, skill_id ASC",
                params,
            ).fetchall()
        return [self._skill(row) for row in rows]

    @staticmethod
    def _mcp_server(row):
        if not row:
            return None
        return {
            "server_id": row["server_id"],
            "name": row["name"],
            "description": row["description"],
            "transport": row["transport"],
            "enabled": bool(row["enabled"]),
            "config": json.loads(row["config"]),
            "secrets": json.loads(row["secrets"]),
            "tools": json.loads(row["tools"]),
            "status": json.loads(row["status"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_mcp_server(self, server_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM task_mcp_servers WHERE server_id=?", (server_id,)).fetchone()
        return self._mcp_server(row)

    def list_mcp_servers(self, search: str = "") -> list[dict]:
        filters, params = [], []
        if search.strip():
            query = search.strip()
            filters.append(
                "(instr(lower(name), lower(?))>0 OR instr(lower(description), lower(?))>0 "
                "OR instr(lower(server_id), lower(?))>0 OR instr(lower(tools), lower(?))>0)"
            )
            params.extend([query, query, query, query])
        where = " WHERE " + " AND ".join(filters) if filters else ""
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM task_mcp_servers" + where + " ORDER BY updated_at DESC, server_id ASC",
                params,
            ).fetchall()
        return [self._mcp_server(row) for row in rows]
