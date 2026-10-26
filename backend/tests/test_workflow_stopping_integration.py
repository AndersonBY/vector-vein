"""Exercise the real task wrappers and runner against disposable SQLite storage."""
import os
import subprocess
import sys
from pathlib import Path


def test_cooperative_stopping_and_terminal_races(tmp_path):
    script = r'''
import sys
import threading
import time
from copy import deepcopy
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from models import Workflow as Model, WorkflowRunRecord, create_tables, database
from utilities.config import cache, config
from utilities.workflow import Workflow
from utilities.workflow_stopping import request_stop, register_child
from utilities.workflow_timeline import reset_run, initialize_timeline
from worker.tasks import task, on_finish
from background_task import workflow_tasks as runner
from celery_worker import app
from api.workflow_api import WorkflowAPI, WorkflowRunRecordAPI
from utilities.workflow_stopping import WorkflowStopped
from unittest.mock import patch
from types import SimpleNamespace

create_tables()
app.conf.update(task_always_eager=True, task_eager_propagates=True)
started, release = threading.Event(), threading.Event()
called = []

@task
def quick(data, node_id):
    called.append(node_id)
    wf = Workflow(data)
    wf.update_node_field_value(node_id, 'output', 'retained output')
    artifact = Path('completed.txt').resolve()
    artifact.write_text('retained artifact')
    wf.get_node(node_id).data['data']['artifacts'] = [{'path': str(artifact)}]
    return wf.data

@task
def slow(data, node_id):
    called.append(node_id)
    started.set()
    assert release.wait(15)
    wf = Workflow(data)
    wf.update_node_field_value(node_id, 'output', 'drained output')
    return wf.data

@task
def downstream(data, node_id):
    called.append(node_id)
    raise AssertionError('downstream must never execute')

runner.task_functions['stopping_test'] = dict(quick=quick, slow=slow, downstream=downstream)

def node(identity, function):
    return {'id': identity, 'type': 'Text', 'category': 'textProcessing',
            'data': {'task_name': 'stopping_test.' + function,
                     'template': {'output': {'value': '', 'is_output': True}}}}

def create(data=None, status='RUNNING'):
    data = deepcopy(data or {'nodes': [], 'edges': []})
    model = Model.create(title='stop test', data=data)
    reset_run(data)
    record = WorkflowRunRecord.create(workflow=model, data=data, status=status)
    data.update(rid=record.rid.hex, wid=model.wid.hex)
    record.data = data
    record.save()
    initialize_timeline(data)
    return record, data

def saved(record):
    return WorkflowRunRecord.get_by_id(record.rid)

try:
    # A queued task cannot enter a node, even if the broker later delivers it.
    queued, data = create({'nodes': [node('queued', 'downstream')], 'edges': []}, 'QUEUED')
    assert request_stop(queued.rid.hex).status == 'STOPPED'
    assert WorkflowRunRecordAPI().stop({'rid': queued.rid.hex})['data']['status'] == 'STOPPED'
    assert WorkflowAPI().stop({'rid': queued.rid.hex, 'wid': queued.workflow.wid.hex})['msg'] == 'STOPPED'
    assert WorkflowRunRecordAPI().stop({'rid': queued.rid.hex, 'wid': []})['status'] == 400
    assert WorkflowAPI().check_status({'rid': queued.rid.hex})['msg'] == 'STOPPED'
    runner.run_workflow.run(data)
    assert 'queued' not in called
    assert request_stop(queued.rid.hex).status == 'STOPPED'
    on_finish(data)
    assert saved(queued).status == 'STOPPED'

    # Real sequential Celery chain: the running node drains, next node never enters.
    definition = {'nodes': [node('quick', 'quick'), node('slow', 'slow'), node('after', 'downstream')],
                  'edges': [{'source': 'quick', 'target': 'slow', 'sourceHandle': 'output', 'targetHandle': 'input'},
                            {'source': 'slow', 'target': 'after', 'sourceHandle': 'output', 'targetHandle': 'input'}]}
    record, data = create(definition)
    errors = []
    def run():
        try:
            runner.run_workflow.run(data)
        except BaseException as exc:
            errors.append(exc)
    thread = threading.Thread(target=run)
    thread.start()
    assert started.wait(15)
    assert request_stop(record.rid.hex).status == 'STOPPING'
    assert WorkflowAPI().check_status({'rid': record.rid.hex})['status'] == 202
    assert WorkflowRunRecordAPI().stop({'rid': record.rid.hex})['data']['status'] == 'STOPPING'
    assert request_stop(record.rid.hex).status == 'STOPPING'
    partial = saved(record)
    assert next(n for n in partial.data['nodes'] if n['id'] == 'quick')['data']['template']['output']['value'] == 'retained output'
    release.set()
    thread.join(20)
    assert not thread.is_alive() and not errors, errors
    result = saved(record)
    assert result.status == 'STOPPED', result.status
    nodes = {n['id']: n for n in result.data['nodes']}
    assert nodes['quick']['data']['template']['output']['value'] == 'retained output'
    assert Path(nodes['quick']['data']['artifacts'][0]['path']).read_text() == 'retained artifact'
    assert nodes['slow']['data']['template']['output']['value'] == 'drained output'
    assert 'after' not in called
    assert result.data['node_timeline']['slow']['status'] == 'SUCCEEDED'
    assert result.data['node_timeline']['after']['status'] == 'STOPPED'
    # Late completion/failure callbacks cannot replace cancellation or prior terminal outcomes.
    Workflow(deepcopy(data)).report_workflow_status(200)
    Workflow(deepcopy(data)).report_workflow_status(500)
    assert saved(record).status == 'STOPPED'
    for status in ('FINISHED', 'FAILED'):
        terminal, terminal_data = create(status=status)
        assert request_stop(terminal.rid.hex).status == status
        Workflow(terminal_data).report_workflow_status(200 if status == 'FAILED' else 500)
        assert saved(terminal).status == status

    # Parallel siblings finish before cancellation becomes terminal and merged results survive.
    started.clear(); release.clear()
    parallel, parallel_data = create({'nodes': [node('parallel-quick', 'quick'), node('parallel-slow', 'slow'), node('parallel-after', 'downstream')],
                                    'edges': [{'source': 'parallel-quick', 'target': 'parallel-after', 'sourceHandle': 'output', 'targetHandle': 'input'},
                                              {'source': 'parallel-slow', 'target': 'parallel-after', 'sourceHandle': 'output', 'targetHandle': 'input'}]})
    thread = threading.Thread(target=lambda: runner.run_workflow.run(parallel_data))
    thread.start()
    assert started.wait(15)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        quick_node = next(n for n in saved(parallel).data['nodes'] if n['id'] == 'parallel-quick')
        if quick_node['data']['template']['output']['value']:
            break
        time.sleep(.01)
    assert quick_node['data']['template']['output']['value']
    assert request_stop(parallel.rid.hex).status == 'STOPPING'
    release.set(); thread.join(20)
    assert not thread.is_alive()
    assert saved(parallel).status == 'STOPPED'
    assert 'parallel-after' not in called
    assert all(n['data']['template']['output']['value'] for n in saved(parallel).data['nodes'] if n['id'] != 'parallel-after')

    # A waiting parent's child is part of its drain, including a child already in flight.
    started.clear(); release.clear()
    parent, parent_data = create()
    child, child_data = create({'nodes': [node('child-slow', 'slow')], 'edges': []})
    with cache.transact():
        register_child(parent.rid.hex, child.rid.hex)
    thread = threading.Thread(target=lambda: slow(child_data, 'child-slow'))
    thread.start(); assert started.wait(15)
    assert request_stop(parent.rid.hex).status == 'STOPPING'
    assert saved(child).status == 'STOPPING'
    release.set(); thread.join(20)
    assert saved(child).status == saved(parent).status == 'STOPPED'

    # Independently cancelled child propagates stop rather than manufacturing a failure.
    independent, independent_data = create({'nodes': [node('nested', 'quick')], 'edges': []})
    @task
    def observe_cancelled_child(data, node_id):
        raise WorkflowStopped()
    observe_cancelled_child(independent_data, 'nested')
    assert saved(independent).status == 'STOPPED'
    assert not saved(independent).data.get('failures')

    # A retry requested after cancellation is not published to the broker.
    retry_record, retry_data = create({'nodes': [node('retry', 'quick')], 'edges': []})
    @task
    def retrying(data, node_id):
        request_stop(data['rid'])
        retrying.retry(data, node_id)
    with patch.object(retrying.celery_task, 'retry', side_effect=AssertionError('no retry may be scheduled')):
        retrying(retry_data, 'retry')
    assert saved(retry_record).status == 'STOPPED'

    # A genuine in-flight failure wins over cancellation and remains terminal.
    failing, failing_data = create({'nodes': [node('failure', 'quick')], 'edges': []})
    @task
    def fail_after_stop(data, node_id):
        request_stop(data['rid'])
        raise ValueError('real in-flight failure')
    try:
        fail_after_stop(failing_data, 'failure')
    except ValueError:
        pass
    else:
        raise AssertionError('original failure must propagate')
    assert saved(failing).status == 'FAILED'
    assert saved(failing).data['failures'][0]['message'] == 'real in-flight failure'
    assert request_stop(failing.rid.hex).status == 'FAILED'

    chat, chat_data = create()
    WorkflowRunRecord.update(run_from='CHAT').where(WorkflowRunRecord.rid == chat.rid).execute()
    message = SimpleNamespace(status='R', metadata={}, save=lambda: None)
    with patch('utilities.workflow_stopping.Message', SimpleNamespace(
            get_or_none=lambda *args: message, mid='mid',
            StatusTypes=SimpleNamespace(RUNNING_WORKFLOW='R', WORKFLOW_FAILED='Z'))):
        assert request_stop(chat.rid.hex).status == 'STOPPED'
    assert message.status == 'Z' and message.metadata['recordStatus'] == 'STOPPED'

    # Simultaneous last-node finish and stop choose a single immutable terminal state.
    for _ in range(8):
        raced, raced_data = create()
        barrier = threading.Barrier(2)
        finisher = threading.Thread(target=lambda: (barrier.wait(), Workflow(deepcopy(raced_data)).report_workflow_status(200)))
        finisher.start(); barrier.wait()
        outcome = request_stop(raced.rid.hex).status
        finisher.join(10)
        assert outcome in ('FINISHED', 'STOPPED')
        assert saved(raced).status == outcome
    print('stopping integration passed')
finally:
    release.set()
    cache.close(); database.close(); config.close()
'''
    environment = {key: value for key, value in os.environ.items()
                   if key not in ("VECTORVEIN_LLM_SETTINGS_FILE", "VECTORVEIN_OUTPUT_DIR")}
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", script,
                             str(Path(__file__).resolve().parents[1])], cwd=tmp_path,
                            env=environment, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "stopping integration passed" in result.stdout
