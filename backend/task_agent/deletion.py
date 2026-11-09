"""Delete quiescent task history while preserving every workspace file."""
from __future__ import annotations

from .projection import build_timeline, project_event


class DeletionConflict(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def validate_tasks(store, tasks):
    from .workflows import TERMINAL, workflow_run_views
    for task in tasks:
        if task['status'] not in {'COMPLETED', 'FAILED', 'INTERRUPTED'}:
            raise DeletionConflict('active_task')
        if any(review.get('status') == 'reviewing' for review in store.risk_reviews(task['tid'])):
            raise DeletionConflict('engine_busy')
        jobs = store.workflow_jobs(task['tid'])
        if jobs and (any(job['result'] is None for job in jobs) or
                     any(run['status'] not in TERMINAL for run in workflow_run_views(store, task['tid']))):
            raise DeletionConflict('active_workflow')
        mcp_jobs = store.mcp_jobs(task['tid'])
        if mcp_jobs and any(
            job.get('result') is None
            or str(job.get('status') or '').upper() in {'ADMITTED', 'DISPATCHING', 'UNKNOWN'}
            or bool((job.get('payload') or {}).get('dispatch_uncertain'))
            for job in mcp_jobs
        ):
            raise DeletionConflict('active_mcp')
        timeline, _ = build_timeline(store.events(task['tid']))
        if any(item.get('command_status') in {'running', 'stopping', 'unknown'} for item in timeline):
            raise DeletionConflict('active_command')


def delete_history(store, task_root, tasks, *, project=None, expected_task_count=None):
    ledger = task_root / 'sessions.db'
    with store.connect() as connection:
        if ledger.exists():
            connection.execute('ATTACH DATABASE ? AS execution', (str(ledger),))
            if connection.execute('PRAGMA execution.user_version').fetchone()[0] != 3:
                raise DeletionConflict('unsupported_store')
        connection.execute('BEGIN IMMEDIATE')
        if project is not None:
            current = connection.execute('SELECT * FROM task_projects WHERE project_id=?', (project['project_id'],)).fetchone()
            if current is None or current['updated_at'] != project['updated_at']:
                raise DeletionConflict('changed')
            current_tasks = connection.execute('SELECT tid,updated_at FROM tasks WHERE project_id=?', (project['project_id'],)).fetchall()
            if len(current_tasks) != expected_task_count:
                raise DeletionConflict('changed')
        else:
            current_tasks = connection.execute('SELECT tid,updated_at FROM tasks WHERE tid=?', (tasks[0]['tid'],)).fetchall()
        if {(row['tid'], row['updated_at']) for row in current_tasks} != {(task['tid'], task['updated_at']) for task in tasks}:
            raise DeletionConflict('changed')
        connection.execute('CREATE TEMP TABLE deleting_tasks(tid TEXT PRIMARY KEY,thread_id TEXT)')
        connection.executemany('INSERT INTO deleting_tasks VALUES(?,?)', [(task['tid'], task['thread_id']) for task in tasks])
        if ledger.exists():
            # vv-agent 0.33.1 has no delete RPC. Fence its pinned SQLite v3 writers before purging history.
            connection.execute('''CREATE TEMP TABLE deleting_sessions AS WITH RECURSIVE owned(session_id) AS (
                SELECT session_id FROM execution.sk_session WHERE session_id IN (SELECT thread_id FROM deleting_tasks)
                UNION SELECT s.session_id FROM execution.sk_session s JOIN owned ON s.parent_session_id=owned.session_id
            ) SELECT session_id FROM owned''')
            busy = connection.execute('''SELECT 1 FROM execution.sk_session WHERE session_id IN (SELECT session_id FROM deleting_sessions)
                AND (phase NOT IN ('idle','closed') OR (lease_until_ms IS NOT NULL AND lease_until_ms>unixepoch('now')*1000)) LIMIT 1''').fetchone()
            pending = connection.execute('''SELECT 1 FROM execution.sk_inbox WHERE session_id IN (SELECT session_id FROM deleting_sessions)
                AND consumed_seq IS NULL LIMIT 1''').fetchone()
            if busy or pending:
                raise DeletionConflict('engine_busy')
            sessions = connection.execute('SELECT session_id FROM deleting_sessions').fetchall()
            if sessions:
                from vv_agent.session.sqlite import SQLiteStore
                from vv_agent.session.projection import project_records
                with SQLiteStore.standalone(str(ledger)) as sdk:
                    for session in sessions:
                        _, records, _ = sdk.read_state(session['session_id'])
                        events = [projected for event in project_records(records) if (projected := project_event(event.to_dict())) is not None]
                        timeline, _ = build_timeline(events)
                        if any(item.get('command_status') in {'running', 'stopping', 'unknown'} for item in timeline):
                            raise DeletionConflict('active_command')
            for table in ('sk_inbox', 'sk_consumer', 'sk_commit', 'sk_record', 'sk_session'):
                connection.execute(f'DELETE FROM execution.{table} WHERE session_id IN (SELECT session_id FROM deleting_sessions)')
        for table in ('task_projection', 'task_events', 'task_commands', 'task_workflow_jobs', 'task_mcp_jobs', 'task_model_failures', 'task_risk_reviews', 'task_completion_effects', 'messages'):
            connection.execute(f'DELETE FROM {table} WHERE task_id IN (SELECT tid FROM deleting_tasks)')
        connection.execute('DELETE FROM tasks WHERE tid IN (SELECT tid FROM deleting_tasks)')
        if project is not None:
            connection.execute("DELETE FROM task_schedules WHERE json_extract(data, '$.project_id')=?", (project['project_id'],))
            connection.execute('DELETE FROM task_projects WHERE project_id=?', (project['project_id'],))
    return {'deleted': True, 'task_ids': [task['tid'] for task in tasks], 'project_id': project['project_id'] if project else None}
