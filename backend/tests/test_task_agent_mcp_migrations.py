"""The MCP execution schema must initialize and upgrade the preceding library schema."""
import sqlite3

from task_agent.store import BusinessStore, SCHEMA_VERSION


def test_fresh_database_initializes_mcp_execution_schema(tmp_path):
    store = BusinessStore(tmp_path / "tasks.db")
    with store.connect() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(task_mcp_jobs)")}
        assert {"job_id", "task_id", "session_id", "status", "result"} <= columns
    assert store.mcp_jobs("missing-task") == []


def test_version_eight_upgrades_and_preserves_existing_data(tmp_path):
    path = tmp_path / "tasks.db"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE tasks (
                tid TEXT PRIMARY KEY, thread_id TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL, goal TEXT NOT NULL, status TEXT NOT NULL,
                current_turn_id TEXT, model_provider TEXT NOT NULL, model TEXT NOT NULL,
                reasoning_effort TEXT NOT NULL, config_snapshot TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, project_id TEXT
            );
            INSERT INTO tasks VALUES (
                'existing-task', 'existing-thread', 'Existing task', 'Preserve this goal',
                'COMPLETED', NULL, 'local', 'fixture', 'default', '{}',
                '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00', NULL
            );
        """)
        connection.execute("CREATE TABLE retained_marker(value TEXT NOT NULL)")
        connection.execute("INSERT INTO retained_marker VALUES ('keep-existing-data')")
        connection.execute("PRAGMA user_version=8")
    for _ in range(2):
        store = BusinessStore(path)
        with store.connect() as connection:
            assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
            assert connection.execute("SELECT value FROM retained_marker").fetchone()[0] == "keep-existing-data"
            task = connection.execute("SELECT * FROM tasks WHERE tid='existing-task'").fetchone()
            assert task["goal"] == "Preserve this goal"
            assert task["status"] == "COMPLETED"
            assert task["hidden"] == 0
        assert store.mcp_jobs("missing-task") == []
