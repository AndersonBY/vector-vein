from __future__ import annotations

from datetime import datetime
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
