"""Exercise live progress and saved history through the real eager Celery DAG."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def test_live_parallel_timeline_failure_history_and_fresh_rerun(tmp_path):
    script = r'''
import json
import sys
import threading
import time
from copy import deepcopy

sys.path.insert(0, sys.argv[1])
from api.utils import run_workflow_common
from api.workflow_api import WorkflowAPI
from background_task.workflow_tasks import task_functions
from celery_worker import app
from models import Workflow, WorkflowRunRecord, create_tables, database
from utilities.config import cache, config
from worker.tasks import task

create_tables()
app.conf.update(task_always_eager=True, task_eager_propagates=False)
entered = {name: threading.Event() for name in ('left', 'right', 'fail')}
release = {name: threading.Event() for name in entered}
second_run = False
executed = []

@task
def timeline_probe(workflow_data, node_id):
    executed.append(node_id)
    if second_run:
        assert not workflow_data.get('failures')
        assert not workflow_data.get('skipped_nodes')
        assert not workflow_data.get('error_task')
        if node_id in ('left', 'right'):
            assert workflow_data['node_timeline']['fail']['status'] == 'PENDING'
            assert workflow_data['node_timeline']['fail']['started_at'] is None
            assert workflow_data['node_timeline']['fail']['finished_at'] is None
    if not second_run and node_id in entered:
        entered[node_id].set()
        assert release[node_id].wait(20), 'test failed to release ' + node_id
    if node_id == 'fail' and not second_run:
        raise ValueError('synthetic failure')
    return workflow_data

task_functions['tools']['timeline_probe'] = timeline_probe
def node(identity):
    return {'id': identity, 'type': 'TimelineProbe', 'category': 'tools',
            'data': {'title': identity, 'task_name': 'tools.timeline_probe',
                     'template': {'api_key': {'value': 'synthetic-input-secret'},
                                  'code': {'value': 'synthetic-source-secret'}}}}
definition = {'nodes': [node(name) for name in ('left', 'right', 'fail', 'downstream')],
              'edges': [{'source': source, 'sourceHandle': 'output', 'target': target, 'targetHandle': 'input'}
                        for source, target in [('left', 'fail'), ('right', 'fail'), ('fail', 'downstream')]]}
model = Workflow.create(title='timeline integration', data=deepcopy(definition))
data = deepcopy(definition)
errors = []
def run():
    try:
        run_workflow_common(data, model, run_from='CLI')
    except Exception as exc:
        errors.append(type(exc).__name__)

thread = threading.Thread(target=run, daemon=True)
thread.start()
try:
    assert entered['left'].wait(20) and entered['right'].wait(20)
    rid = data['rid']
    def snapshot():
        response = WorkflowAPI().check_status({'rid': rid})
        assert response['status'] == 202, response
        assert isinstance(response['data']['finished_nodes'], list)
        timeline = response['data']['node_timeline']
        assert set(timeline) == {'left', 'right', 'fail', 'downstream'}
        allowed = {'node_id', 'node_type', 'title', 'task_name', 'status', 'started_at', 'finished_at', 'run_time'}
        for identity, entry in timeline.items():
            assert set(entry) <= allowed, entry
            assert entry['node_id'] == identity
        encoded = json.dumps(timeline)
        assert 'synthetic-input-secret' not in encoded and 'synthetic-source-secret' not in encoded
        return timeline
    live = snapshot()
    assert live['left']['status'] == live['right']['status'] == 'RUNNING'
    assert live['fail']['status'] == live['downstream']['status'] == 'PENDING'
    assert live['left']['started_at'] > 1_000_000_000_000
    assert live['left']['finished_at'] is None
    release['left'].set()
    deadline = time.monotonic() + 10
    while True:
        live = snapshot()
        if live['left']['status'] == 'SUCCEEDED':
            break
        assert time.monotonic() < deadline, live
        threading.Event().wait(.01)
    assert live['right']['status'] == 'RUNNING'
    assert live['left']['finished_at'] >= live['left']['started_at']
    release['right'].set()
    assert entered['fail'].wait(20)
    live = snapshot()
    assert live['left']['status'] == live['right']['status'] == 'SUCCEEDED'
    assert live['fail']['status'] == 'RUNNING'
finally:
    for event in release.values():
        event.set()
    thread.join(25)
assert not thread.is_alive()
assert 'downstream' not in executed
database.close()
saved = WorkflowRunRecord.get_by_id(rid)
assert saved.status == 'FAILED', saved.data
old_data = deepcopy(saved.data)
timeline = old_data['node_timeline']
assert timeline['left']['status'] == timeline['right']['status'] == 'SUCCEEDED'
assert timeline['fail']['status'] == 'FAILED'
assert timeline['downstream']['status'] in ('PENDING', 'SKIPPED')
for identity in ('left', 'right', 'fail'):
    entry = timeline[identity]
    assert entry['started_at'] <= entry['finished_at']
    assert entry['run_time'] >= 0
assert old_data['failures'][0]['node_id'] == 'fail'
assert WorkflowAPI().check_status({'rid': rid})['data']['data']['node_timeline'] == timeline

# Replay the saved definition through the same public launch helper.
second_run = True
data = deepcopy(old_data)
data['skipped_nodes'] = ['downstream']
new_rid = run_workflow_common(data, model, run_from='CLI')
database.close()
fresh = WorkflowRunRecord.get_by_id(new_rid)
assert new_rid != rid and fresh.status == 'FINISHED', fresh.data
assert not fresh.data.get('failures') and not fresh.data.get('skipped_nodes')
assert all(entry['status'] == 'SUCCEEDED' for entry in fresh.data['node_timeline'].values())
assert WorkflowRunRecord.get_by_id(rid).data == old_data
assert len(list(WorkflowRunRecord.select())) == 2
cache.close()
database.close()
config.close()
print('timeline integration passed')
'''
    environment = {key: value for key, value in os.environ.items()
                   if key not in ("VECTORVEIN_LLM_SETTINGS_FILE", "VECTORVEIN_OUTPUT_DIR")}
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", script, str(Path(__file__).resolve().parents[1])],
        cwd=tmp_path, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "timeline integration passed" in result.stdout
