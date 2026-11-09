from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4

import pytest
from peewee import SqliteDatabase
from peewee_migrate import Router


MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


@pytest.mark.parametrize("previous_migration", [None, "001_init", "004_add_embedding_model"])
def test_real_migrations_initialize_and_upgrade_database(tmp_path, previous_migration):
    database = SqliteDatabase(tmp_path / "my_database.db")
    try:
        router = Router(database, migrate_dir=MIGRATIONS)
        if previous_migration:
            router.run(previous_migration)
            workflow = router.migrator.orm["workflow"]
            workflow.create(
                wid=uuid4(),
                title="Existing workflow",
                data='{"nodes": [], "edges": []}',
                images="[]",
                version=None,
                create_time=datetime.now(),
                update_time=datetime.now(),
            )

        # A new router matches the next application startup with pending migrations.
        router = Router(database, migrate_dir=MIGRATIONS)
        router.run()
        assert router.done == sorted(path.stem for path in MIGRATIONS.glob("[0-9][0-9][0-9]_*.py"))
        assert {"tool_call_data", "version"} <= {column.name for column in database.get_columns("workflow")}
        assert "workflow_version" in {column.name for column in database.get_columns("workflowrunrecord")}
        assert "embedding_provider" in {column.name for column in database.get_columns("user_vector_database")}
        if previous_migration:
            assert database.execute_sql("SELECT title, data, version, tool_call_data FROM workflow").fetchall() == [
                ("Existing workflow", '{"nodes": [], "edges": []}', 1, "{}")
            ]
        assert Router(database, migrate_dir=MIGRATIONS).run() == []
    finally:
        database.close()


def test_conversation_removal_deletes_history_and_preserves_other_workspaces(tmp_path):
    from diskcache import Cache
    database = SqliteDatabase(tmp_path / "upgrade.db", pragmas={"foreign_keys": 1})
    try:
        Router(database, migrate_dir=MIGRATIONS).run("005_add_workflow_version")
        database.execute_sql("ALTER TABLE workflowrunrecord ADD COLUMN source_message TEXT")
        database.execute_sql("CREATE TABLE agent (aid INTEGER PRIMARY KEY)")
        database.execute_sql("CREATE TABLE conversation (cid INTEGER PRIMARY KEY, agent_id INTEGER REFERENCES agent(aid))")
        database.execute_sql("CREATE TABLE message (mid INTEGER PRIMARY KEY, conversation_id INTEGER REFERENCES conversation(cid), parent_id INTEGER REFERENCES message(mid))")
        database.execute_sql("CREATE TABLE chatdraft (id INTEGER PRIMARY KEY, conversation_id INTEGER REFERENCES conversation(cid))")
        for table in ("agent_workflow_through", "agent_workflowtemplate_through", "conversation_workflow_through", "conversation_workflowtemplate_through"):
            database.execute_sql(f'CREATE TABLE "{table}" (id INTEGER PRIMARY KEY)')
        database.execute_sql("INSERT INTO agent VALUES (1)")
        database.execute_sql("INSERT INTO conversation VALUES (1, 1)")
        database.execute_sql("INSERT INTO message VALUES (1, 1, NULL), (2, 1, 1)")
        database.execute_sql("INSERT INTO chatdraft VALUES (1, 1)")
        settings = {"agent": {"auto_title": True}, "microphone_device": 2,
                    "shortcuts": {"__global__": {"open_task_agent": "ctrl+1"}, "old-agent": {"new_chat": "ctrl+2"}},
                    "task_agent_approval": {"model": "retained"}, "workflow": {"tool_call_data_generate_model": ["OpenAI", "kept"]}}
        database.execute_sql("INSERT INTO setting (data, create_time, update_time) VALUES (?, ?, ?)",
                             (json.dumps(settings), datetime.now(), datetime.now()))
        identities = {source: uuid4().hex for source in ("CHAT", "WEB", "API")}
        for source, identity in identities.items():
            database.execute_sql("INSERT INTO workflowrunrecord (rid, status, data, start_time, used_credits, run_from, workflow_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                 (identity, "FINISHED", "{}", datetime.now(), 0, source, 1))
        with Cache(tmp_path / "cache") as cache:
            cache.set("chat_response:old", {"text": "deleted"})
            cache.set("conversation-title:old", "deleted")
            cache.set("workflow:record:" + identities["CHAT"], "deleted")
            cache.set("workflow:record:" + identities["WEB"], "retained")
            cache.set("task-agent-test", "retained")
        Router(database, migrate_dir=MIGRATIONS).run()
        assert not {"agent", "conversation", "message", "chatdraft"} & set(database.get_tables())
        assert not any(table.startswith(("agent_", "conversation_")) for table in database.get_tables())
        assert "source_message" not in {column.name for column in database.get_columns("workflowrunrecord")}
        assert {row[0] for row in database.execute_sql("SELECT run_from FROM workflowrunrecord")} == {"WEB", "API"}
        saved = json.loads(database.execute_sql("SELECT data FROM setting").fetchone()[0])
        assert "agent" not in saved and "microphone_device" not in saved
        assert saved["shortcuts"] == {"__global__": {"open_task_agent": "ctrl+1"}}
        assert saved["task_agent_approval"] == settings["task_agent_approval"]
        assert saved["workflow"] == settings["workflow"]
        with Cache(tmp_path / "cache") as cache:
            assert set(cache) == {"workflow:record:" + identities["WEB"], "task-agent-test"}
        assert Router(database, migrate_dir=MIGRATIONS).run() == []
    finally:
        database.close()
