import json
import sqlite3
import time
from types import SimpleNamespace

import pytest

from task_agent.deletion import DeletionConflict, delete_history
from task_agent.service import TaskAgentService
from task_agent.store import BusinessStore
from vv_agent.session.records import SessionSpec
from vv_agent.session.sqlite import SQLiteStore


@pytest.fixture
def service(tmp_path):
    process = SimpleNamespace(forget_tasks=lambda ids: None)
    return TaskAgentService(tmp_path, data_path=tmp_path / 'state', process=process)


def task(service, tid='one', project_id=None, status='COMPLETED'):
    service.store.create_task({
        'tid': tid, 'thread_id': tid, 'title': tid, 'goal': 'Goal', 'status': status,
        'current_turn_id': None, 'model_provider': 'mock', 'model': 'mock',
        'reasoning_effort': 'default', 'config_snapshot': {}, 'created_at': 'v1',
        'updated_at': 'v1', 'project_id': project_id,
    })
    service.store.upsert_message({'task_id': tid, 'turn_id': 'turn', 'role': 'user', 'content': tid, 'status': 'completed'})
    service.store.save_command(tid, 'command', 'thread/start', {})
    service.store.save_state(tid, {})
    with service.store.connect() as db:
        db.execute('INSERT INTO task_events VALUES(?,?,?,?,?)', (tid, 'event', 1, 0, json.dumps({'id': 'event', 'kind': 'assistant', 'turn_id': 'turn', 'text': 'Done'})))
        db.execute('INSERT INTO task_model_failures VALUES(?,?,?)', (tid, 'call', '{}'))
        db.execute('INSERT INTO task_risk_reviews VALUES(?,?,?,?)', (tid, 'request', 'fingerprint', '{}'))
    return service.store.get_task(tid)


def delete(service, tid='one'):
    return service.delete_task({'task_id': tid, 'expected_updated_at': 'v1'})


def sessions(service):
    path = service.task_root / 'sessions.db'
    with SQLiteStore.standalone(str(path)) as sdk:
        sdk.install_schema()
        for sid, parent in [('one', None), ('child', 'one'), ('grandchild', 'child'), ('other', None)]:
            with sdk.atomic() as tx:
                tx.create(SessionSpec(session_id=sid, principal='test', workspace=str(service.workspace),
                                      parent_session_id=parent, parent_operation_id='op' if parent else None), consumers=('events',))
    return path


def test_deletes_all_history_and_descendants_but_keeps_other_tasks_and_files(service, tmp_path):
    task(service)
    task(service, 'other')
    ledger = sessions(service)
    files = [tmp_path / 'project' / 'source.txt', service.task_root / 'workspaces' / 'one' / 'output.txt',
             service.task_root / 'attachments' / 'one' / 'input.txt']
    for path in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('keep', encoding='utf-8')
    service._subscriptions = {('client', 'one'), ('client', 'other')}
    assert delete(service)['task_ids'] == ['one']
    assert service._subscriptions == {('client', 'other')}
    assert service.store.get_task('one') is None
    assert service.store.get_task('other')
    for table in ['messages', 'task_projection', 'task_events', 'task_commands', 'task_workflow_jobs', 'task_model_failures', 'task_risk_reviews']:
        with service.store.connect() as db:
            assert db.execute(f'SELECT count(*) FROM {table} WHERE task_id=?', ('one',)).fetchone()[0] == 0
    with sqlite3.connect(ledger) as db:
        assert db.execute('SELECT session_id FROM sk_session').fetchall() == [('other',)]
        for table in ['sk_record', 'sk_commit', 'sk_consumer']:
            assert {row[0] for row in db.execute(f'SELECT DISTINCT session_id FROM {table}')} == {'other'}
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
    assert all(path.read_text(encoding='utf-8') == 'keep' for path in files)
    assert BusinessStore(service.store.path).get_task('one') is None


@pytest.mark.parametrize('count', [0, 3, 105])
def test_project_deletes_every_task_without_pagination_and_preserves_roots(service, tmp_path, count):
    root = tmp_path / 'project'
    root.mkdir()
    file = root / 'source.txt'
    file.write_text('keep', encoding='utf-8')
    project = service.save_project({'project_id': 'p', 'roots': [str(root)]})
    service.save_project({'project_id': 'other', 'roots': [str(root)]})
    for index in range(count):
        task(service, f't{index}', 'p')
    task(service, 'independent')
    task(service, 'other-task', 'other')
    result = service.delete_project({'project_id': 'p', 'expected_updated_at': project['updated_at'], 'expected_task_count': count})
    assert len(result['task_ids']) == count
    assert service.store.get_project('p') is None
    assert service.store.get_project('other')
    assert {t['tid'] for t in service.store.list_tasks()} == {'independent', 'other-task'}
    assert file.read_text(encoding='utf-8') == 'keep'


@pytest.mark.parametrize('status', ['PENDING', 'PROCESSING', 'PAUSED', 'WAITING_FOR_USER', 'WAITING_FOR_APPROVAL', 'WAITING_FOR_WORKFLOW'])
def test_active_tasks_cannot_be_deleted(service, status):
    task(service, status=status)
    with pytest.raises(DeletionConflict, match='active_task'):
        delete(service)
    assert service.store.get_task('one')


@pytest.mark.parametrize('guard', ['phase', 'lease', 'inbox', 'schema'])
def test_sdk_busy_children_or_unknown_schema_block_entire_deletion(service, guard):
    task(service)
    ledger = sessions(service)
    with sqlite3.connect(ledger) as db:
        if guard == 'phase':
            db.execute("UPDATE sk_session SET phase='active' WHERE session_id='child'")
        elif guard == 'lease':
            db.execute("UPDATE sk_session SET lease_owner='worker',lease_until_ms=? WHERE session_id='child'", (int(time.time() * 1000) + 60000,))
        elif guard == 'inbox':
            db.execute("INSERT INTO sk_inbox VALUES('child','input',1,'user',?, ?,0,0,NULL)", (b'{}', '0' * 64))
        else:
            db.execute('PRAGMA user_version=999')
    with pytest.raises(DeletionConflict, match='unsupported_store' if guard == 'schema' else 'engine_busy'):
        delete(service)
    assert service.store.list_messages('one')
    with sqlite3.connect(ledger) as db:
        assert db.execute('SELECT count(*) FROM sk_session').fetchone()[0] == 4


def test_stale_confirmation_and_transaction_snapshot_do_not_delete(service, tmp_path):
    project = service.save_project({'project_id': 'p', 'roots': [str(tmp_path)]})
    original = task(service, project_id='p')
    with pytest.raises(DeletionConflict, match='changed'):
        service.delete_project({'project_id': 'p', 'expected_updated_at': project['updated_at'], 'expected_task_count': 0})
    with pytest.raises(DeletionConflict, match='changed'):
        service.delete_task({'task_id': 'one', 'expected_updated_at': 'stale'})
    service.store.update_task('one', title='Changed')
    with pytest.raises(DeletionConflict, match='changed'):
        delete_history(service.store, service.task_root, [original])
    assert service.store.get_task('one')


@pytest.mark.parametrize('guard', ['risk', 'workflow', 'command'])
def test_active_work_prevents_deletion(service, monkeypatch, guard):
    task(service)
    if guard == 'risk':
        with service.store.connect() as db:
            db.execute('UPDATE task_risk_reviews SET data=?', (json.dumps({'status': 'reviewing'}),))
        code = 'engine_busy'
    elif guard == 'workflow':
        monkeypatch.setattr(service.store, 'workflow_jobs', lambda tid: [{'result': None}])
        code = 'active_workflow'
    else:
        monkeypatch.setattr(service.store, 'events', lambda tid: [{
            'id': 'command', 'turn_id': 'turn', 'tool_call_id': 'command', 'kind': 'tool_call_completed',
            'tool_name': 'bash', 'status': 'success', 'result': {'preview': json.dumps({'session_id': 'bg', 'status': 'running'})},
        }])
        code = 'active_command'
    with pytest.raises(DeletionConflict, match=code):
        delete(service)
    assert service.store.get_task('one')


def test_sql_failure_rolls_back_both_databases(service):
    task(service)
    ledger = sessions(service)
    with service.store.connect() as db:
        db.execute("CREATE TRIGGER reject_deletion BEFORE DELETE ON tasks BEGIN SELECT RAISE(ABORT,'test failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match='test failure'):
        delete(service)
    assert service.store.list_messages('one')
    with sqlite3.connect(ledger) as db:
        assert db.execute('SELECT count(*) FROM sk_session').fetchone()[0] == 4


def test_api_validates_ids_and_maps_conflicts(service, monkeypatch):
    from api.task_agent_api import TaskAgentAPI
    monkeypatch.setattr('api.task_agent_api.task_agent_service', lambda: service)
    api = TaskAgentAPI()
    assert api.delete_task({'task_id': '../bad'})['status'] == 400
    assert api.delete_task({'task_id': 'missing'})['status'] == 404
    task(service, status='PROCESSING')
    response = api.delete_task({'task_id': 'one', 'expected_updated_at': 'v1'})
    assert response['status'] == 409
    assert response['data']['deletion_error'] == 'active_task'
    project = service.save_project({'project_id': 'p', 'roots': [str(service.workspace)]})
    assert api.delete_project({'project_id': 'p', 'expected_updated_at': 'stale', 'expected_task_count': 0})['status'] == 409
    assert api.delete_project({'project_id': 'p', 'expected_updated_at': project['updated_at'], 'expected_task_count': True})['status'] == 400
    monkeypatch.setattr(service, 'delete_task', lambda payload: (_ for _ in ()).throw(sqlite3.OperationalError('locked')))
    assert api.delete_task({'task_id': 'one'})['status'] == 503


@pytest.mark.parametrize('status', ['FAILED', 'INTERRUPTED'])
def test_other_terminal_states_can_be_deleted(service, status):
    task(service, status=status)
    assert delete(service)['deleted']


def test_project_with_busy_task_is_not_partially_deleted(service):
    project = service.save_project({'project_id': 'p', 'roots': [str(service.workspace)]})
    task(service, 'done', 'p')
    task(service, 'busy', 'p', status='PROCESSING')
    with pytest.raises(DeletionConflict, match='active_task'):
        service.delete_project({'project_id': 'p', 'expected_updated_at': project['updated_at'], 'expected_task_count': 2})
    assert service.store.get_project('p')
    assert service.store.get_task('done') and service.store.get_task('busy')


def test_real_appserver_deletes_completed_task_and_stays_deleted_after_restart(tmp_path):
    import subprocess
    import sys
    import threading
    from http.server import ThreadingHTTPServer
    from pathlib import Path
    from test_task_agent import MockModelHandler

    server = ThreadingHTTPServer(('127.0.0.1', 0), MockModelHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        result = subprocess.run(
            [sys.executable, '-X', 'utf8', str(Path(__file__).with_name('task_agent_flow_smoke.py')),
             str(tmp_path), str(server.server_port), '--delete'],
            capture_output=True, text=True, encoding='utf-8', timeout=120,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        assert json.loads(result.stdout) == {'status': 'COMPLETED', 'messages': 4}
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
