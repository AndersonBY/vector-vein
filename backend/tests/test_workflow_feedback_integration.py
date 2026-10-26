"""Real-run feedback checkpoints, including process restart and nested workflows."""
import os
import subprocess
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]


def run_script(script, cwd):
    environment = {key: value for key, value in os.environ.items()
                   if key not in ("VECTORVEIN_LLM_SETTINGS_FILE", "VECTORVEIN_OUTPUT_DIR")}
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", script, str(BACKEND)],
                            cwd=cwd, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert result.returncode == 0, result.stderr + result.stdout
    return result.stdout


def test_feedback_sequence_parallel_validation_stop_and_nested_runs(tmp_path):
    script = r'''
import sys
import threading
import time
from copy import deepcopy
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
from models import Workflow as Model, WorkflowRunRecord, create_tables, database
from utilities.config import cache, config
from utilities.workflow import Workflow
from utilities.workflow_stopping import request_stop, register_child
from utilities.workflow_feedback import wake_parent
from utilities.workflow_timeline import reset_run, initialize_timeline
from worker.tasks import task
from worker.tasks.control_flows import workflow_selector
from background_task import workflow_tasks as runner
from celery_worker import app
from api.workflow_api import WorkflowAPI, WorkflowRunRecordAPI

create_tables()
app.conf.update(task_always_eager=True, task_eager_propagates=True)
called = []
entered, release = threading.Event(), threading.Event()

@task
def effect(data, node_id):
    called.append(node_id)
    wf = Workflow(data)
    wf.update_node_field_value(node_id, 'output', 'upstream retained')
    return wf.data

@task
def slow(data, node_id):
    called.append(node_id)
    entered.set()
    assert release.wait(15)
    wf = Workflow(data)
    wf.update_node_field_value(node_id, 'output', 'slow retained')
    return wf.data

@task
def fail(data, node_id):
    raise ValueError('real sibling failure')

runner.task_functions['feedback_test'] = dict(effect=effect, slow=slow, fail=fail)

def node(identity, feedback=False, function='effect'):
    return {'id': identity, 'type': 'HumanFeedback' if feedback else 'Test', 'category': 'controlFlows',
            'data': {'task_name': 'control_flows.human_feedback' if feedback else 'feedback_test.' + function,
                     'template': {'hint_message': {'value': 'Please review'}, 'human_input': {'value': 'stale prefilled'},
                                  'output': {'value': '', 'is_output': True}}}}

def edge(source, target):
    return {'source': source, 'target': target, 'sourceHandle': 'output', 'targetHandle': 'hint_message'}

def create(nodes, edges):
    data = dict(nodes=nodes, edges=edges)
    model = Model.create(title='feedback test', data=deepcopy(data))
    reset_run(data)
    record = WorkflowRunRecord.create(workflow=model, data=data, status='RUNNING')
    data.update(rid=record.rid.hex, wid=model.wid.hex)
    record.data = data; record.save(); initialize_timeline(data)
    return record, data

def saved(record):
    return WorkflowRunRecord.get_by_id(record.rid)

def answer(record, *items):
    return WorkflowAPI().resume({'rid': record.rid.hex, 'human_feedback_nodes': [dict(node_id=identity, content=content) for identity, content in items]})

try:
    record, data = create([node('before'), node('first', True), node('middle'), node('second', True), node('after')],
                          [edge('before', 'first'), edge('first', 'middle'), edge('middle', 'second'), edge('second', 'after')])
    runner.run_workflow.run(data)
    paused = saved(record)
    assert paused.status == 'PAUSED', paused.status
    assert paused.data['pending_feedback_nodes'] == ['first']
    assert called == ['before']
    assert next(n for n in paused.data['nodes'] if n['id'] == 'first')['data']['template']['hint_message']['value'] == 'upstream retained'
    assert next(n for n in paused.data['nodes'] if n['id'] == 'first')['data']['template']['human_input']['value'] == ''
    assert WorkflowAPI().check_status({'rid': record.rid.hex})['status'] == 102
    for invalid in (None, [], [{'node_id':'first','content':'  '}], [{'node_id':'after','content':'wrong'}],
                    [{'node_id':'first','content':'one'}, {'node_id':'first','content':'duplicate'}]):
        assert WorkflowRunRecordAPI().resume({'rid': record.rid.hex, 'human_feedback_nodes': invalid})['status'] == 400
    assert answer(record, ('first', 'accepted first'))['status'] == 200
    paused = saved(record)
    assert paused.status == 'PAUSED' and paused.data['pending_feedback_nodes'] == ['second'], paused.data
    assert called == ['before', 'middle']
    assert answer(record, ('first', 'late duplicate'))['status'] == 400
    assert answer(record, ('second', 'accepted second'))['status'] == 200
    assert saved(record).status == 'FINISHED' and called == ['before', 'middle', 'after']
    assert answer(record, ('second', 'late'))['status'] == 409

    # Both feedback nodes enter the current batch; the running sibling drains before PAUSED.
    parallel, parallel_data = create([node('p1', True), node('p2', True), node('slow', function='slow'), node('p-after')],
                                     [edge('p1', 'p-after'), edge('p2', 'p-after'), edge('slow', 'p-after')])
    thread = threading.Thread(target=lambda: runner.run_workflow.run(parallel_data))
    thread.start(); assert entered.wait(15)
    for _ in range(100):
        if len(saved(parallel).data.get('pending_feedback_nodes', [])) == 2:
            break
        time.sleep(.02)
    assert saved(parallel).status == 'RUNNING'
    assert answer(parallel, ('p1', 'one'), ('p2', 'two'))['status'] == 409
    release.set(); thread.join(20); assert not thread.is_alive()
    paused = saved(parallel)
    assert paused.status == 'PAUSED' and set(paused.data['pending_feedback_nodes']) == {'p1', 'p2'}, paused.data
    assert answer(parallel, ('p1', 'partial'))['status'] == 400
    assert next(n for n in paused.data['nodes'] if n['id'] == 'slow')['data']['template']['output']['value'] == 'slow retained'
    # Concurrent submissions publish one continuation, and old chain generations are inert.
    dispatched = []
    barrier = threading.Barrier(2)
    responses = []
    def submit():
        barrier.wait()
        responses.append(answer(parallel, ('p1', 'one'), ('p2', 'two'))['status'])
    with patch('celery_tasks.run_workflow.delay', side_effect=lambda snapshot: dispatched.append(deepcopy(snapshot))):
        threads = [threading.Thread(target=submit) for _ in range(2)]
        for candidate in threads: candidate.start()
        for candidate in threads: candidate.join(10)
    assert sorted(responses) == [200,409] and len(dispatched) == 1, responses
    runner.run_workflow.run(parallel_data)
    assert 'p-after' not in called
    runner.run_workflow.run(dispatched[0])
    assert saved(parallel).status == 'FINISHED' and called.count('p-after') == 1
    assert called.count('slow') == 1

    stopped, stopped_data = create([node('stop', True), node('forbidden')], [edge('stop', 'forbidden')])
    runner.run_workflow.run(stopped_data)
    assert saved(stopped).status == 'PAUSED'
    assert request_stop(stopped.rid.hex).status == 'STOPPED'
    assert answer(stopped, ('stop', 'late'))['status'] == 409
    assert 'forbidden' not in called

    raced, raced_data = create([node('race-feedback',True),node('race-forbidden')],[edge('race-feedback','race-forbidden')])
    runner.run_workflow.run(raced_data)
    gate = threading.Barrier(2)
    queued = []
    with patch('celery_tasks.run_workflow.delay',side_effect=lambda snapshot: queued.append(deepcopy(snapshot))):
        contender=threading.Thread(target=lambda: (gate.wait(),answer(raced,('race-feedback','accepted'))))
        contender.start();gate.wait();request_stop(raced.rid.hex);contender.join(10)
    for snapshot in queued: runner.run_workflow.run(snapshot)
    assert saved(raced).status=='STOPPED' and 'race-forbidden' not in called

    failed, failed_data=create([node('failure-feedback',True),node('failure',function='fail'),node('failure-after')],
                              [edge('failure-feedback','failure-after'),edge('failure','failure-after')])
    try: runner.run_workflow.run(failed_data)
    except Exception: pass
    assert saved(failed).status=='FAILED' and saved(failed).data['failures'][0]['message']=='real sibling failure'
    assert 'failure-after' not in called

    # A conditional branch already skipped before this checkpoint stays skipped on resume.
    skipped, skipped_data = create([node('skip', True), node('needed', True)], [])
    skipped_data['skipped_nodes'] = ['skip']
    runner.run_workflow.run(skipped_data)
    assert saved(skipped).data['pending_feedback_nodes'] == ['needed']
    assert answer(skipped, ('needed', 'answer'))['status'] == 200
    assert saved(skipped).status == 'FINISHED'

    # A nested selector pauses durably without scheduling/exhausting polling retries.
    child_model = Model.create(title='child feedback', data={'nodes':[node('child-feedback', True)], 'edges':[]})
    selector = {'id':'selector','type':'WorkflowSelector','category':'controlFlows','data':{
        'task_name':'control_flows.workflow_selector','template':{'input':{'value':'review'},'template':{'value':''},
        'llm_model':{'value':''},'workflow_ids':{'value':[{'id':child_model.wid.hex}]},'output':{'value':'','is_output':True}}}}
    parent, parent_data = create([selector, node('parent-after')], [edge('selector','parent-after')])
    with patch.object(workflow_selector.celery_task, 'retry', side_effect=AssertionError('paused child cannot consume retries')):
        runner.run_workflow.run(parent_data)
    paused = saved(parent)
    assert paused.status == 'PAUSED', paused.data
    child_rid = paused.data['pending_feedback_runs'][0]
    child = WorkflowRunRecord.get_by_id(child_rid)
    assert child.status == 'PAUSED'
    assert answer(child, ('child-feedback','approved child'))['status'] == 200
    assert saved(parent).status == 'FINISHED', saved(parent).data
    assert called.count('parent-after') == 1

    # Publishing uncertainty retains an actionable checkpoint and the accepted input.
    recovery, recovery_data = create([node('recover-feedback',True),node('recover-after')],[edge('recover-feedback','recover-after')])
    runner.run_workflow.run(recovery_data)
    old_delivery = []
    with patch('celery_tasks.run_workflow.delay', side_effect=lambda snapshot: (old_delivery.append(deepcopy(snapshot)), (_ for _ in ()).throw(ConnectionError('publish uncertain')))[1]):
        assert answer(recovery,('recover-feedback','keep accepted answer'))['status'] == 500
    ready = saved(recovery)
    assert ready.status == 'PAUSED' and ready.data['feedback_resume_ready']
    assert ready.data['feedback_answers']['recover-feedback'] == 'keep accepted answer'
    assert answer(recovery)['status'] == 200
    runner.run_workflow.run(old_delivery[0])
    assert saved(recovery).status == 'FINISHED' and called.count('recover-after') == 1

    # A child cancelled while both child and parent are paused cancels its parent too.
    cancel_parent, cancel_data = create([deepcopy(selector),node('cancel-after')],[edge('selector','cancel-after')])
    runner.run_workflow.run(cancel_data)
    cancelled_child = saved(cancel_parent).data['pending_feedback_runs'][0]
    assert request_stop(cancelled_child).status == 'STOPPED'
    assert saved(cancel_parent).status == 'STOPPED'
    assert 'cancel-after' not in called

    # A real child failure is not hidden behind another child's pending human input.
    waiting_child,waiting_data=create([node('other-child-feedback',True)],[])
    runner.run_workflow.run(waiting_data)
    failed_parent,failed_parent_data=create([],[])
    failed_parent_data.update(pending_feedback_runs=[failed.rid.hex,waiting_child.rid.hex],_feedback_waiting=True)
    WorkflowRunRecord.update(status='PAUSED',data=failed_parent_data).where(WorkflowRunRecord.rid==failed_parent.rid).execute()
    with cache.transact():
        register_child(failed_parent.rid.hex,failed.rid.hex)
        register_child(failed_parent.rid.hex,waiting_child.rid.hex)
    wake_parent(failed.rid.hex)
    assert saved(failed_parent).status=='FAILED'
    assert saved(waiting_child).status=='STOPPED'
    assert saved(failed_parent).data['failures'][0]['message']=='real sibling failure'
    stop_failed_parent,stop_failed_data=create([],[])
    with cache.transact(): register_child(stop_failed_parent.rid.hex,failed.rid.hex)
    assert request_stop(stop_failed_parent.rid.hex).status=='FAILED'
    assert saved(stop_failed_parent).data['failures'][0]['message']=='real sibling failure'

    # Failure drains another admitted child and reaches grandparents without losing evidence.
    entered.clear();release.clear()
    deep_child,deep_child_data=create([node('deep-slow',function='slow')],[])
    deep_parent,deep_parent_data=create([],[])
    grandparent,grandparent_data=create([],[])
    for current,current_data,children in ((deep_parent,deep_parent_data,[failed.rid.hex,deep_child.rid.hex]),
                                          (grandparent,grandparent_data,[deep_parent.rid.hex])):
        current_data.update(pending_feedback_runs=children,_feedback_waiting=True)
        WorkflowRunRecord.update(status='PAUSED',data=current_data).where(WorkflowRunRecord.rid==current.rid).execute()
        with cache.transact():
            for child_id in children:register_child(current.rid.hex,child_id)
    thread=threading.Thread(target=lambda:slow(deep_child_data,'deep-slow'))
    thread.start();assert entered.wait(15)
    wake_parent(failed.rid.hex)
    assert saved(deep_parent).status=='STOPPING'
    release.set();thread.join(20);assert not thread.is_alive()
    assert saved(deep_parent).status==saved(grandparent).status=='FAILED'
    assert saved(grandparent).data['failures'][0]['message']=='real sibling failure'

    chat,chat_data=create([node('chat-feedback',True)],[])
    WorkflowRunRecord.update(run_from='CHAT').where(WorkflowRunRecord.rid==chat.rid).execute()
    message=SimpleNamespace(status='R',metadata={},save=lambda:None)
    with patch('utilities.workflow_feedback.Message',SimpleNamespace(mid='mid',get_or_none=lambda *args:message,
            StatusTypes=SimpleNamespace(RUNNING_WORKFLOW='R'))):
        runner.run_workflow.run(chat_data)
    assert saved(chat).status=='PAUSED' and message.status=='R'
    assert message.metadata['recordStatus']=='PAUSED' and 'workflow_result' not in message.metadata
    print('feedback runner passed')
finally:
    release.set(); cache.close(); database.close(); config.close()
'''
    assert "feedback runner passed" in run_script(script, tmp_path)


def test_feedback_checkpoint_resumes_in_new_process_without_replaying_effects(tmp_path):
    first = r'''
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from models import Workflow as Model, WorkflowRunRecord, create_tables, database
from utilities.config import cache, config
from api.utils import run_workflow_common
from celery_worker import app
app.conf.update(task_always_eager=True, task_eager_propagates=True)
create_tables()
def node(identity, kind, function, fields):
    return {'id':identity,'type':kind,'category':'tools','data':{'task_name':function,'template':{key:{'value':value} for key,value in fields.items()}}}
nodes=[node('effect','ProgrammingFunction','tools.programming_function',{'language':'python','code':"from pathlib import Path\ndef main():\n p=Path('effects.txt'); p.write_text(p.read_text()+'x' if p.exists() else 'x'); return 'retained'",'output':''}),
       node('feedback','HumanFeedback','control_flows.human_feedback',{'hint_message':'review','human_input':'stale','output':''}),
       node('after','ProgrammingFunction','tools.programming_function',{'language':'python','code':'def main(value): return value.upper()','value':'','output':''})]
nodes[0]['data']['template']['output']['is_output']=True
nodes[2]['data']['template']['output']['is_output']=True
data={'nodes':nodes,'edges':[{'source':'effect','target':'feedback','sourceHandle':'output','targetHandle':'hint_message'},
                           {'source':'feedback','target':'after','sourceHandle':'output','targetHandle':'value'}]}
model=Model.create(title='restart feedback',data=data)
rid=run_workflow_common(data,model)
record=WorkflowRunRecord.get_by_id(rid)
assert record.status=='PAUSED',record.data
Path('rid.txt').write_text(rid)
assert Path('effects.txt').read_text()=='x'
cache.close();database.close();config.close()
'''
    run_script(first, tmp_path)
    second = r'''
import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from models import WorkflowRunRecord,database
from utilities.config import cache,config
from api.workflow_api import WorkflowAPI
from celery_worker import app
app.conf.update(task_always_eager=True,task_eager_propagates=True)
rid=Path('rid.txt').read_text()
record=WorkflowRunRecord.get_by_id(rid)
assert record.status=='PAUSED'
result=WorkflowAPI().resume({'rid':rid,'human_feedback_nodes':[{'node_id':'feedback','content':'approved'}]})
assert result['status']==200,result
record=WorkflowRunRecord.get_by_id(rid)
assert record.status=='FINISHED',record.data
assert Path('effects.txt').read_text()=='x'
nodes={node['id']:node for node in record.data['nodes']}
assert nodes['after']['data']['template']['output']['value']=='APPROVED'
assert nodes['effect']['data']['template']['output']['value']=='retained'
cache.close();database.close();config.close()
'''
    run_script(second, tmp_path)
