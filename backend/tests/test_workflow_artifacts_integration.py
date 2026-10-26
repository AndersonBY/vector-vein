"""Real Document producers, parallel merge, saved records and artifact API."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def test_parallel_documents_survive_failure_and_rerun_keeps_artifacts_scoped(tmp_path):
    script = r'''
import os
import sys
import threading
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

os.environ['VECTORVEIN_OUTPUT_DIR'] = str(Path.cwd() / 'outputs')
sys.path.insert(0, sys.argv[1])
from api.utils import run_workflow_common
from api.workflow_api import WorkflowRunRecordAPI
from background_task.workflow_tasks import task_functions
from celery_worker import app
from models import Workflow, WorkflowRunRecord, create_tables, database
from utilities.config import cache, config
from worker.tasks import task

create_tables()
app.conf.update(task_always_eager=True, task_eager_propagates=False)
blocked, release = threading.Event(), threading.Event()
fail = False
@task
def artifact_gate(workflow_data, node_id):
    if fail:
        blocked.set()
        assert release.wait(20)
        raise ValueError('synthetic downstream failure')
    return workflow_data
task_functions['tools']['artifact_gate'] = artifact_gate

def document(identity):
    fields = {'file_name': identity, 'content': 'synthetic document', 'export_type': '.txt', 'overwrite': False}
    template = {key: {'value': value} for key, value in fields.items()}
    template['output'] = {'value': '', 'is_output': True}
    return {'id': identity, 'type': 'Document', 'category': 'output',
            'data': {'title': identity, 'task_name': 'output.document', 'template': template}}
definition = {'nodes': [document('left'), document('right'),
                       {'id': 'gate', 'type': 'ArtifactGate', 'category': 'tools',
                        'data': {'task_name': 'tools.artifact_gate', 'template': {}}}],
              'edges': [{'source': identity, 'sourceHandle': 'output', 'target': 'gate', 'targetHandle': identity}
                        for identity in ('left', 'right')]}
model = Workflow.create(title='artifact integration', data=deepcopy(definition))
api = WorkflowRunRecordAPI()
def rows(rid):
    result = api.list_artifacts({'rid': rid})
    assert result['status'] == 200, result
    return result['data']['artifacts']
def assert_two(rid):
    artifacts = rows(rid)
    assert len(artifacts) == 2, artifacts
    assert {item['sources'][0]['node_id'] for item in artifacts} == {'left', 'right'}
    assert all(item['exists'] and item['size'] > 0 and Path(item['path']).suffix == '.txt' for item in artifacts)
    return artifacts

success_rid = run_workflow_common(deepcopy(definition), model, run_from='CLI')
database.close()
success = WorkflowRunRecord.get_by_id(success_rid)
assert success.status == 'FINISHED', success.data
success_snapshot = deepcopy(success.data)
success_rows = assert_two(success_rid)
assert all(node['data'].get('artifacts') for node in success.data['nodes'] if node['id'] in ('left', 'right'))

# Block only the downstream task, exposing completed parallel files through cache.
fail = True
data = deepcopy(success_snapshot)
errors = []
def run_failed():
    try:
        run_workflow_common(data, model, run_from='CLI')
    except Exception as exc:
        errors.append(type(exc).__name__)
thread = threading.Thread(target=run_failed, daemon=True)
thread.start()
try:
    assert blocked.wait(20)
    failed_rid = data['rid']
    live_rows = assert_two(failed_rid)
    assert {item['path'] for item in live_rows}.isdisjoint(item['path'] for item in success_rows)
finally:
    release.set()
    thread.join(25)
assert not thread.is_alive()
database.close()
failed = WorkflowRunRecord.get_by_id(failed_rid)
assert failed.status == 'FAILED', failed.data
failed_snapshot = deepcopy(failed.data)
assert rows(failed_rid) == live_rows
assert failed.data['failures'][0]['node_id'] == 'gate'

# Both producers fail validation before writing; their old output values remain inputs.
data = deepcopy(failed_snapshot)
for node in data['nodes']:
    if node['id'] in ('left', 'right'):
        node['data']['template']['export_type']['value'] = '.unsupported'
empty_rid = run_workflow_common(data, model, run_from='CLI')
database.close()
empty = WorkflowRunRecord.get_by_id(empty_rid)
assert empty.status == 'FAILED'
assert rows(empty_rid) == []
assert all(node['data']['artifacts'] == [] for node in empty.data['nodes'])
assert WorkflowRunRecord.get_by_id(success_rid).data == success_snapshot
assert WorkflowRunRecord.get_by_id(failed_rid).data == failed_snapshot

calls = []
from utilities import workflow_artifacts as artifacts
with patch.object(artifacts.sys, 'platform', 'win32'), patch.object(artifacts.os, 'startfile', calls.append, create=True):
    existing = success_rows[0]['path']
    assert api.open_artifact({'rid': success_rid, 'path': existing, 'action': 'open'})['status'] == 200
    assert calls == [existing]
    calls.clear()
    assert api.open_artifact({'rid': failed_rid, 'path': existing, 'action': 'open'})['status'] == 404
    arbitrary = Path.cwd() / 'unrelated.txt'
    arbitrary.write_text('synthetic unrelated', encoding='utf8')
    assert api.open_artifact({'rid': success_rid, 'path': str(arbitrary), 'action': 'open'})['status'] == 404
    assert not calls
    Path(existing).rename(Path(existing).with_suffix('.moved'))
    missing = next(item for item in rows(success_rid) if item['path'] == existing)
    assert not missing['exists'] and missing['size'] is None and missing['parent_exists']
    assert missing['sources'] == success_rows[0]['sources']
    assert api.open_artifact({'rid': success_rid, 'path': existing, 'action': 'open'})['status'] == 404
    assert not calls
    assert api.open_artifact({'rid': success_rid, 'path': existing, 'action': 'folder'})['status'] == 200
    assert calls == [str(Path(existing).parent)]
assert api.list_artifacts({'rid': '00000000000000000000000000000000'})['status'] == 404
cache.close()
database.close()
config.close()
print('artifact integration passed')
'''
    environment = {key: value for key, value in os.environ.items()
                   if key not in ("VECTORVEIN_LLM_SETTINGS_FILE", "VECTORVEIN_OUTPUT_DIR")}
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", script, str(Path(__file__).resolve().parents[1])],
        cwd=tmp_path, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "artifact integration passed" in result.stdout
