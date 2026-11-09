"""Real initialization regressions for the desktop's relative ./data default."""
from __future__ import annotations

import json
import os
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from knowledge_base import KnowledgeError, KnowledgeService
from knowledge_base.migration import migrate_legacy


def legacy_database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    kb_id, document_id = uuid4().hex, uuid4().hex
    db = sqlite3.connect(path)
    try:
        db.executescript("""
            CREATE TABLE user_vector_database(id INTEGER,vid TEXT,name TEXT,
                embedding_provider TEXT,embedding_model TEXT,embedding_size INTEGER);
            CREATE TABLE user_object(oid TEXT,title TEXT,vector_database_id INTEGER,raw_data TEXT);
        """)
        db.execute("INSERT INTO user_vector_database VALUES(1,?,'Legacy KB','synthetic','synthetic',3)", (kb_id,))
        db.execute("INSERT INTO user_object VALUES(?,'Note',1,?)",
                   (document_id, json.dumps({"text": "Recovered evidence 中文"})))
        db.commit()
    finally:
        db.close()
    return kb_id, document_id


def test_relative_legacy_path_migrates_existing_database(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace 中文 with spaces"
    kb_id, document_id = legacy_database(workspace / "data" / "my_database.db")
    # Restore cwd before pytest cleans the temporary directory on Windows.
    with monkeypatch.context() as patch:
        patch.chdir(workspace)
        owner = KnowledgeService(Path("./data/knowledge-base"), legacy_path=Path("./data/my_database.db"),
                                 start_worker=False)
        try:
            assert owner.get(kb_id)["name"] == "Legacy KB"
            assert owner.get_item(kb_id, document_id)["status"] == "unindexed"
            assert owner.read_document([kb_id], document_id)["text"] == "Recovered evidence 中文"
            assert owner.run_pending() == 0
            migrate_legacy(owner, Path("./data/my_database.db"))
            assert owner.get(kb_id)["document_count"] == 1
        finally:
            owner.close()


def test_relative_legacy_path_still_rejects_reparse_ancestor(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace 中文 with spaces"
    legacy_database(workspace / "data" / "my_database.db")
    owner = KnowledgeService(tmp_path / "owner", start_worker=False)
    original_lstat = Path.lstat
    try:
        with monkeypatch.context() as patch:
            patch.chdir(workspace)
            def lstat(path, *args, **kwargs):
                if path == workspace / "data":
                    return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
                return original_lstat(path, *args, **kwargs)
            patch.setattr(Path, "lstat", lstat)
            with pytest.raises(KnowledgeError) as rejected:
                migrate_legacy(owner, Path("./data/my_database.db"))
            assert rejected.value.code == "unsafe_path"
            assert owner.list() == {"bases": []}
    finally:
        owner.close()


@pytest.mark.parametrize("has_legacy_rows", [False, True])
def test_real_api_bridge_lists_kbs_with_default_relative_data_path(tmp_path, has_legacy_rows):
    workspace = tmp_path / "desktop 中文 with spaces"
    workspace.mkdir()
    backend = Path(__file__).resolve().parents[1]
    code = """
import sys
sys.path.insert(0, sys.argv[1])
seed = sys.argv[2] == '1'
from utilities.config import config, cache
assert config.data_path == './data'
from models import create_tables, database, UserVectorDatabase, UserObject
create_tables()
legacy = UserVectorDatabase.create(name='Existing KB', embedding_provider='synthetic',
                                  embedding_model='synthetic', embedding_size=3) if seed else None
document = UserObject.create(title='Existing document', data_type='TEXT', vector_database=legacy,
                             raw_data={'text': 'Recovered evidence'}) if seed else None
from knowledge_base import knowledge_service, stop_knowledge_service
try:
    from api_bridge import APIBridge
    bridge = APIBridge()
    response = bridge.knowledge_base__list({})
    assert response['status'] == 200, response
    expected = [(legacy.vid.hex, 'Existing KB')] if seed else []
    assert [(row['id'], row['name']) for row in response['data']['bases']] == expected
    owner = knowledge_service()
    if seed:
        assert owner.get_item(legacy.vid.hex, document.oid.hex)['status'] == 'unindexed'
        assert owner.read_document([legacy.vid.hex], document.oid.hex)['text'] == 'Recovered evidence'
    assert owner._db.execute('SELECT count(*) FROM jobs').fetchone()[0] == 0
    assert owner.vectors.client is None
    assert bridge.knowledge_base__list({})['status'] == 200
    assert UserVectorDatabase.select().count() == int(seed)
    assert UserObject.select().count() == int(seed)
    print('REAL_KB_LIST_OK')
finally:
    stop_knowledge_service()
    database.close()
    cache.close()
"""
    # Fresh process and cwd: use real config, models, bridge and singleton, with no
    # inherited model credentials or external settings-file overrides.
    env = {key: value for key, value in os.environ.items()
           if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "TEMP", "TMP", "COMSPEC"}}
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(backend), "1" if has_legacy_rows else "0"], cwd=workspace,
                            env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "REAL_KB_LIST_OK" in result.stdout
