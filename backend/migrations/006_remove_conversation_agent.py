"""Permanently remove the retired conversation Agent and its history."""
import json
from pathlib import Path
import re


def remove_cache(database):
    cache_path = Path(database.database).parent / "cache"
    if not (cache_path / "cache.db").is_file():
        return
    from diskcache import Cache
    tables = set(database.get_tables())
    retained = {row[0] for row in database.execute_sql("SELECT rid FROM workflowrunrecord")} if "workflowrunrecord" in tables else set()
    with Cache(cache_path) as cache:
        for key in cache.iterkeys():
            if not isinstance(key, str):
                continue
            if key == "has_start_recording" or key.startswith(("chat_response:", "conversation-title:", "screen_shot_path_")):
                cache.delete(key)
            elif key.startswith(("workflow:record:", "workflow_record")):
                identity = re.search(r"[0-9a-f]{32}", key)
                if identity and identity.group() not in retained:
                    cache.delete(key)


def migrate(migrator, database, *, fake=False):
    if fake:
        return
    from utilities.upgrade_backup import ensure_v1_upgrade_backup

    ensure_v1_upgrade_backup(database, legacy_only=True)
    database.execute_sql("PRAGMA secure_delete=ON")
    tables = set(database.get_tables())
    if "workflowrunrecord" in tables:
        columns = {column.name for column in database.get_columns("workflowrunrecord")}
        if "run_from" in columns:
            database.execute_sql("DELETE FROM workflowrunrecord WHERE run_from = ?", ("CHAT",))
        if "source_message" in columns:
            database.execute_sql('ALTER TABLE "workflowrunrecord" DROP COLUMN "source_message"')
    for table in (
        "agent_workflow_through", "agent_workflowtemplate_through",
        "conversation_workflow_through", "conversation_workflowtemplate_through",
        "chatdraft", "message", "conversation", "agent",
    ):
        database.execute_sql(f'DROP TABLE IF EXISTS "{table}"')
    if "setting" in tables:
        for identity, raw in database.execute_sql("SELECT id, data FROM setting").fetchall():
            try:
                data = json.loads(raw)
            except (ValueError, TypeError):
                continue
            if not isinstance(data, dict):
                continue
            previous = dict(data)
            data.pop("agent", None)
            data.pop("microphone_device", None)
            shortcuts = data.get("shortcuts")
            if isinstance(shortcuts, dict):
                data["shortcuts"] = {"__global__": shortcuts["__global__"]} if "__global__" in shortcuts else {}
            if data != previous:
                database.execute_sql("UPDATE setting SET data = ? WHERE id = ?", (json.dumps(data, ensure_ascii=False), identity))
    remove_cache(database)


def rollback(migrator, database, *, fake=False):
    raise RuntimeError("Conversation Agent history removal cannot be reversed.")
